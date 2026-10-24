from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class CPUInfo:
    name: str = "Desconhecido"
    vendor: str = "Desconhecido"
    architecture: str = "Desconhecida"
    physical_cores: int = 0
    logical_cores: int = 0
    max_clock_mhz: int = 0
    socket: str = "Desconhecido"
    virtualization: bool | None = None
    instruction_sets: list[str] = field(default_factory=list)
    cache_l2_kb: int = 0
    cache_l3_kb: int = 0


@dataclass(slots=True)
class MainboardInfo:
    manufacturer: str = "Desconhecido"
    product: str = "Desconhecido"
    version: str = ""
    serial: str = ""
    bios_vendor: str = "Desconhecido"
    bios_version: str = "Desconhecida"
    bios_date: str = ""


@dataclass(slots=True)
class MemoryModule:
    slot: str = "Desconhecido"
    manufacturer: str = "Desconhecido"
    part_number: str = ""
    serial: str = ""
    capacity_gb: float = 0.0
    speed_mhz: int = 0
    configured_speed_mhz: int = 0
    memory_type: str = "Desconhecida"


@dataclass(slots=True)
class GPUInfo:
    name: str = "Desconhecida"
    vendor: str = "Desconhecido"
    vram_gb: float = 0.0
    driver: str = ""
    backend: str = "CPU"
    compute_capability: str = ""


@dataclass(slots=True)
class StorageInfo:
    name: str = "Desconhecido"
    kind: str = "Desconhecido"
    size_gb: float = 0.0
    free_gb: float = 0.0
    interface: str = ""


@dataclass(slots=True)
class SystemInfo:
    hostname: str = "Desconhecido"
    os: str = "Desconhecido"
    os_version: str = ""
    kernel: str = ""
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    machine: str = ""
    python: str = ""
    power_supply: str = "Não detectável por software"
    case: str = "Não detectável por software"
    cooler: str = "Não detectável por software"
    ups: str = "Não detectado"


@dataclass(slots=True)
class HardwareReport:
    system: SystemInfo = field(default_factory=SystemInfo)
    cpu: CPUInfo = field(default_factory=CPUInfo)
    mainboard: MainboardInfo = field(default_factory=MainboardInfo)
    memory_modules: list[MemoryModule] = field(default_factory=list)
    gpus: list[GPUInfo] = field(default_factory=list)
    storage: list[StorageInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    collected_at: str = field(default_factory=utc_now)

    @property
    def best_vram_gb(self) -> float:
        return max((g.vram_gb for g in self.gpus), default=0.0)

    @property
    def total_storage_free_gb(self) -> float:
        return sum(d.free_gb for d in self.storage)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AIModel:
    model_id: str
    display_name: str
    family: str = "Desconhecida"
    task: str = "text-generation"
    parameters_b: float = 0.0
    quantization_bits: int = 4
    min_ram_gb: float = 0.0
    recommended_ram_gb: float = 0.0
    min_vram_gb: float = 0.0
    recommended_vram_gb: float = 0.0
    disk_gb: float = 0.0
    context_length: int = 0
    quality_score: float = 0.0
    popularity_score: float = 0.0
    license: str = "Desconhecida"
    gated: bool = False
    source: str = "curated"
    source_url: str = ""
    updated_at: str = ""
    runtime: str = "llama.cpp / Transformers"
    notes: str = ""
    confidence: str = "estimado"
    deployment: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityResult:
    model: AIModel
    status: str
    score: float
    mode: str
    reasons: list[str]
    bottlenecks: list[str]
    estimated_tokens_per_second: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass(slots=True)
class ComponentRecommendation:
    category: str
    product: str
    specification: str
    reason: str
    estimated_price_brl: tuple[int, int]
    search_links: dict[str, str]
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BuildRecommendation:
    target_model: AIModel
    tier: str
    components: list[ComponentRecommendation]
    total_price_brl: tuple[int, int]
    caveats: list[str]
    generated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
