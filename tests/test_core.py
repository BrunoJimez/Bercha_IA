from __future__ import annotations

from pathlib import Path

import pytest

from bercha_livrenexo.builder import PCBuilder, shopping_links
from bercha_livrenexo.catalog import CatalogDB, hf_item_to_model
from bercha_livrenexo.models import AIModel, CPUInfo, GPUInfo, HardwareReport, StorageInfo, SystemInfo
from bercha_livrenexo.recommender import CompatibilityEngine
from bercha_livrenexo.reports import export_report, report_payload


def hardware(ram: float = 32, vram: float = 16, disk: float = 500) -> HardwareReport:
    return HardwareReport(
        system=SystemInfo(total_ram_gb=ram, available_ram_gb=ram / 2, os="Teste"),
        cpu=CPUInfo(name="CPU de teste", physical_cores=8, logical_cores=16, instruction_sets=["AVX2"]),
        gpus=[GPUInfo(name="GPU de teste", vendor="NVIDIA", vram_gb=vram, backend="CUDA")],
        storage=[StorageInfo(name="SSD", size_gb=1000, free_gb=disk)],
    )


def model(**overrides: object) -> AIModel:
    values = dict(model_id="org/test-8b", display_name="Test 8B Q4", parameters_b=8,
                  min_ram_gb=8, recommended_ram_gb=16, min_vram_gb=6,
                  recommended_vram_gb=10, disk_gb=6, quality_score=80)
    values.update(overrides)
    return AIModel(**values)


def test_gpu_compatible():
    result = CompatibilityEngine().evaluate(hardware(), model())
    assert result.status == "Excelente"
    assert result.mode == "GPU"
    assert result.score >= 90


def test_cpu_fallback_and_incompatible():
    fallback = CompatibilityEngine().evaluate(hardware(ram=24, vram=2), model())
    assert fallback.mode == "CPU/híbrido"
    impossible = CompatibilityEngine().evaluate(hardware(ram=4, vram=2), model())
    assert impossible.status == "Incompatível"
    assert impossible.bottlenecks


def test_cloud_model_does_not_request_local_hardware():
    result = CompatibilityEngine().evaluate(hardware(ram=1, vram=0), model(deployment="cloud"))
    assert result.status == "Nuvem/API"


def test_huggingface_metadata_inference():
    parsed = hf_item_to_model({
        "id": "acme/Reasoner-7B-GGUF-Q4_K_M", "pipeline_tag": "text-generation",
        "downloads": 100_000, "likes": 900, "tags": ["gguf", "license:apache-2.0"],
        "config": {"max_position_embeddings": 32768}, "lastModified": "2026-01-01T00:00:00Z",
    })
    assert parsed.parameters_b == 7
    assert parsed.quantization_bits == 4
    assert parsed.min_ram_gb > parsed.disk_gb
    assert parsed.context_length == 32768
    assert parsed.license == "apache-2.0"


def test_catalog_preserves_curated_record(tmp_path: Path):
    database = CatalogDB(tmp_path / "catalog.sqlite3")
    curated = model(source="curated", quantization_bits=4, quality_score=99)
    online = model(source="Hugging Face", quantization_bits=4, quality_score=2)
    database.upsert_models([curated])
    database.upsert_models([online])
    assert database.get_model(curated.model_id).quality_score == 99
    database.close()


def test_builder_has_complete_safe_configuration():
    build = PCBuilder().build(model(), hardware())
    categories = {component.category for component in build.components}
    assert {"GPU", "Processador", "Placa-mãe", "Memória RAM", "Armazenamento", "Fonte", "Cooler", "Gabinete", "Nobreak/UPS"} <= categories
    assert build.total_price_brl[0] < build.total_price_brl[1]
    assert all(component.search_links for component in build.components)


def test_shop_urls_encode_slashes():
    links = shopping_links("gabinete mid/full")
    assert "%2F" in links["Mercado Livre"]


@pytest.mark.parametrize("suffix", [".json", ".txt", ".html"])
def test_report_exports_and_creates_parent(tmp_path: Path, suffix: str):
    hw = hardware()
    result = CompatibilityEngine().evaluate(hw, model())
    payload = report_payload(hw, [result], PCBuilder().build(model(), hw))
    output = tmp_path / "nested" / f"report{suffix}"
    export_report(output, payload)
    assert output.exists()
    assert output.stat().st_size > 200
