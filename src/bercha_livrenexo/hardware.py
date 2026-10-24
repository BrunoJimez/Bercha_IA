from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .models import (
    CPUInfo,
    GPUInfo,
    HardwareReport,
    MainboardInfo,
    MemoryModule,
    StorageInfo,
    SystemInfo,
)
from .util import safe_float, safe_int


MEMORY_TYPES = {
    20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 30: "LPDDR4",
    34: "DDR5", 35: "LPDDR5",
}


def _run(args: list[str], timeout: int = 15) -> str:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, creationflags=flags,
        )
        return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class HardwareScanner:
    """Coleta conservadora: dado ausente continua explicitamente desconhecido."""

    def scan(self) -> HardwareReport:
        if sys.platform == "win32":
            report = self._scan_windows()
        elif sys.platform == "darwin":
            report = self._scan_macos()
        else:
            report = self._scan_linux()
        self._enrich_portable(report)
        return report

    def _scan_windows(self) -> HardwareReport:
        script = r"""
$ErrorActionPreference='SilentlyContinue'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,Manufacturer,Architecture,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,SocketDesignation,VirtualizationFirmwareEnabled,L2CacheSize,L3CacheSize
$board = Get-CimInstance Win32_BaseBoard | Select-Object -First 1 Manufacturer,Product,Version,SerialNumber
$bios = Get-CimInstance Win32_BIOS | Select-Object -First 1 Manufacturer,SMBIOSBIOSVersion,ReleaseDate
$memory = @(Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Manufacturer,PartNumber,SerialNumber,Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType)
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID)
$disks = @(Get-CimInstance Win32_DiskDrive | Select-Object Model,MediaType,Size,InterfaceType)
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,TotalVisibleMemorySize,FreePhysicalMemory,OSArchitecture
$battery = @(Get-CimInstance Win32_Battery | Select-Object Name,BatteryStatus,EstimatedChargeRemaining)
[PSCustomObject]@{cpu=$cpu;board=$board;bios=$bios;memory=$memory;gpus=$gpus;disks=$disks;os=$os;battery=$battery} | ConvertTo-Json -Depth 5 -Compress
"""
        raw = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], 25)
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = {}
        cpu_data = data.get("cpu") or {}
        board = data.get("board") or {}
        bios = data.get("bios") or {}
        os_data = data.get("os") or {}
        report = HardwareReport(
            system=SystemInfo(
                hostname=socket.gethostname(), os=os_data.get("Caption") or platform.system(),
                os_version=f"{os_data.get('Version', '')} build {os_data.get('BuildNumber', '')}".strip(),
                kernel=platform.release(),
                total_ram_gb=safe_float(os_data.get("TotalVisibleMemorySize")) / 1024 / 1024,
                available_ram_gb=safe_float(os_data.get("FreePhysicalMemory")) / 1024 / 1024,
                machine=os_data.get("OSArchitecture") or platform.machine(), python=platform.python_version(),
                ups="Bateria/UPS detectado" if data.get("battery") else "Não detectado",
            ),
            cpu=CPUInfo(
                name=(cpu_data.get("Name") or "Desconhecido").strip(),
                vendor=cpu_data.get("Manufacturer") or "Desconhecido",
                architecture=str(cpu_data.get("Architecture", platform.machine())),
                physical_cores=safe_int(cpu_data.get("NumberOfCores")),
                logical_cores=safe_int(cpu_data.get("NumberOfLogicalProcessors")),
                max_clock_mhz=safe_int(cpu_data.get("MaxClockSpeed")),
                socket=cpu_data.get("SocketDesignation") or "Desconhecido",
                virtualization=cpu_data.get("VirtualizationFirmwareEnabled"),
                cache_l2_kb=safe_int(cpu_data.get("L2CacheSize")),
                cache_l3_kb=safe_int(cpu_data.get("L3CacheSize")),
            ),
            mainboard=MainboardInfo(
                manufacturer=board.get("Manufacturer") or "Desconhecido",
                product=board.get("Product") or "Desconhecido", version=board.get("Version") or "",
                serial=board.get("SerialNumber") or "", bios_vendor=bios.get("Manufacturer") or "Desconhecido",
                bios_version=bios.get("SMBIOSBIOSVersion") or "Desconhecida",
                bios_date=str(bios.get("ReleaseDate") or ""),
            ),
        )
        for item in _as_list(data.get("memory")):
            report.memory_modules.append(MemoryModule(
                slot=item.get("DeviceLocator") or "Desconhecido",
                manufacturer=(item.get("Manufacturer") or "Desconhecido").strip(),
                part_number=(item.get("PartNumber") or "").strip(), serial=(item.get("SerialNumber") or "").strip(),
                capacity_gb=safe_float(item.get("Capacity")) / 1024**3, speed_mhz=safe_int(item.get("Speed")),
                configured_speed_mhz=safe_int(item.get("ConfiguredClockSpeed")),
                memory_type=MEMORY_TYPES.get(safe_int(item.get("SMBIOSMemoryType")), "Desconhecida"),
            ))
        for item in _as_list(data.get("gpus")):
            name = item.get("Name") or "Desconhecida"
            vendor = "NVIDIA" if "nvidia" in name.lower() else "AMD" if any(x in name.lower() for x in ("amd", "radeon")) else "Intel" if "intel" in name.lower() else "Desconhecido"
            report.gpus.append(GPUInfo(
                name=name, vendor=vendor,
                vram_gb=safe_float(item.get("AdapterRAM")) / 1024**3,
                driver=item.get("DriverVersion") or "", backend={"NVIDIA": "CUDA", "AMD": "ROCm/DirectML", "Intel": "OpenVINO/DirectML"}.get(vendor, "CPU"),
            ))
        for item in _as_list(data.get("disks")):
            report.storage.append(StorageInfo(
                name=item.get("Model") or "Desconhecido", kind=item.get("MediaType") or "Desconhecido",
                size_gb=safe_float(item.get("Size")) / 1000**3, interface=item.get("InterfaceType") or "",
            ))
        self._nvidia_details(report)
        return report

    def _scan_linux(self) -> HardwareReport:
        meminfo: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                meminfo[key] = safe_int(value.split()[0])
        except OSError:
            pass
        cpu_data: dict[str, str] = {}
        try:
            block = Path("/proc/cpuinfo").read_text(errors="replace").split("\n\n", 1)[0]
            cpu_data = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        except OSError:
            pass
        flags = (cpu_data.get("flags") or cpu_data.get("Features") or "").split()
        cpu = CPUInfo(
            name=(cpu_data.get("model name") or cpu_data.get("Hardware") or platform.processor() or "Desconhecido").strip(),
            vendor=(cpu_data.get("vendor_id") or "Desconhecido").strip(), architecture=platform.machine(),
            physical_cores=os.cpu_count() or 0, logical_cores=os.cpu_count() or 0,
            instruction_sets=[x.upper() for x in flags if x in {"avx", "avx2", "avx512f", "sse4_2", "neon", "asimd"}],
        )
        board = MainboardInfo(
            manufacturer=self._read_first("/sys/class/dmi/id/board_vendor"),
            product=self._read_first("/sys/class/dmi/id/board_name"),
            version=self._read_first("/sys/class/dmi/id/board_version"),
            bios_vendor=self._read_first("/sys/class/dmi/id/bios_vendor"),
            bios_version=self._read_first("/sys/class/dmi/id/bios_version"),
            bios_date=self._read_first("/sys/class/dmi/id/bios_date"),
        )
        report = HardwareReport(system=SystemInfo(
            hostname=socket.gethostname(), os=platform.system(), os_version=platform.version(),
            kernel=platform.release(), total_ram_gb=meminfo.get("MemTotal", 0) / 1024**2,
            available_ram_gb=meminfo.get("MemAvailable", 0) / 1024**2,
            machine=platform.machine(), python=platform.python_version(),
        ), cpu=cpu, mainboard=board)
        self._nvidia_details(report)
        return report

    def _scan_macos(self) -> HardwareReport:
        raw = _run(["system_profiler", "SPHardwareDataType", "SPDisplaysDataType", "-json"], 25)
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        hw = (_as_list(data.get("SPHardwareDataType")) or [{}])[0]
        total_bytes = safe_float(hw.get("physical_memory", "0").split()[0]) * (1024**3 if "GB" in str(hw.get("physical_memory")) else 1024**2)
        report = HardwareReport(
            system=SystemInfo(hostname=socket.gethostname(), os="macOS", os_version=platform.mac_ver()[0],
                              kernel=platform.release(), total_ram_gb=total_bytes / 1024**3,
                              machine=platform.machine(), python=platform.python_version()),
            cpu=CPUInfo(name=hw.get("chip_type") or hw.get("cpu_type") or platform.processor(),
                        vendor="Apple" if "Apple" in str(hw) else "Intel", architecture=platform.machine(),
                        physical_cores=safe_int(hw.get("number_processors") or os.cpu_count()), logical_cores=os.cpu_count() or 0),
            mainboard=MainboardInfo(manufacturer="Apple", product=hw.get("machine_model") or "Mac", serial=hw.get("serial_number") or ""),
        )
        for gpu in _as_list(data.get("SPDisplaysDataType")):
            vram_text = str(gpu.get("spdisplays_vram") or gpu.get("spdisplays_vram_shared") or "0")
            report.gpus.append(GPUInfo(name=gpu.get("sppci_model") or "Apple GPU", vendor="Apple",
                                       vram_gb=report.system.total_ram_gb if "shared" in vram_text.lower() else safe_float(vram_text.split()[0]),
                                       backend="Metal"))
        return report

    @staticmethod
    def _read_first(path: str) -> str:
        try:
            return Path(path).read_text(errors="replace").strip()
        except OSError:
            return "Desconhecido"

    def _nvidia_details(self, report: HardwareReport) -> None:
        if not shutil.which("nvidia-smi"):
            return
        query = "name,memory.total,driver_version,compute_cap"
        raw = _run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"], 10)
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            name, memory, driver = parts[:3]
            capability = parts[3] if len(parts) > 3 else ""
            replacement = GPUInfo(name=name, vendor="NVIDIA", vram_gb=safe_float(memory) / 1024,
                                  driver=driver, backend="CUDA", compute_capability=capability)
            match = next((i for i, gpu in enumerate(report.gpus) if gpu.name.lower() == name.lower() or "nvidia" in gpu.name.lower()), None)
            if match is None:
                report.gpus.append(replacement)
            else:
                report.gpus[match] = replacement

    def _enrich_portable(self, report: HardwareReport) -> None:
        try:
            usage = shutil.disk_usage(Path.home())
            if report.storage:
                report.storage[0].free_gb = usage.free / 1000**3
            else:
                report.storage.append(StorageInfo(name=str(Path.home().anchor), kind="Sistema",
                                                  size_gb=usage.total / 1000**3, free_gb=usage.free / 1000**3))
        except OSError:
            pass
        try:
            import cpuinfo  # type: ignore
            info = cpuinfo.get_cpu_info()
            flags = info.get("flags") or []
            report.cpu.instruction_sets = sorted({str(x).upper() for x in flags if x.lower() in {"avx", "avx2", "avx512f", "sse4_2", "neon", "asimd"}})
        except (ImportError, OSError, ValueError):
            pass
        if not report.gpus:
            report.gpus.append(GPUInfo(name="Sem GPU dedicada detectada", vendor="CPU", backend="CPU"))
        if report.system.total_ram_gb <= 0:
            report.warnings.append("Não foi possível medir a memória RAM total.")
        if any(g.vendor in {"AMD", "Intel"} and g.vram_gb <= 0 for g in report.gpus):
            report.warnings.append("O sistema operacional não informou a VRAM de uma GPU integrada; a análise será conservadora.")


def quick_benchmark(duration: float = 0.7) -> dict[str, float | int | str]:
    """Microbenchmark comparável apenas entre execuções do Bercha LivreNexo."""
    size = 64
    a = [((i * 17) % 101) / 101 for i in range(size * size)]
    b = [((i * 29) % 103) / 103 for i in range(size * size)]
    loops = 0
    checksum = 0.0
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        for row in range(size):
            base = row * size
            for col in range(0, size, 8):
                value = 0.0
                for k in range(size):
                    value += a[base + k] * b[k * size + col]
                checksum += value
        loops += 1
    elapsed = time.perf_counter() - start
    operations = loops * size * (size // 8) * size * 2
    return {
        "score": int(operations / elapsed / 1000),
        "operations_per_second": int(operations / elapsed),
        "elapsed_seconds": round(elapsed, 3),
        "threads": 1,
        "checksum": round(checksum, 3),
        "note": "Pontuação interna; não equivale a tokens/s nem a benchmarks de terceiros.",
    }
