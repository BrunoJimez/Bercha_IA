from __future__ import annotations

import json
import math
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .models import AIModel
from .util import app_data_dir, safe_float, safe_int


Progress = Callable[[int, str], None]
USER_AGENT = "BerchaLivreNexo/0.1 (+https://github.com/BrunoJimez/bercha-livrenexo)"


CURATED_MODELS = [
    # O BerchaScore inicial e editorial; o usuário pode importar suas próprias notas.
    AIModel("openai/gpt-oss-120b", "GPT-OSS 120B (MXFP4)", "GPT-OSS", parameters_b=117.0, quantization_bits=4,
            min_ram_gb=80, recommended_ram_gb=128, min_vram_gb=48, recommended_vram_gb=80, disk_gb=65,
            quality_score=96, license="Apache-2.0", source_url="https://huggingface.co/openai/gpt-oss-120b", runtime="Transformers / vLLM", confidence="documentado"),
    AIModel("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "DeepSeek R1 Distill Qwen 32B Q4", "DeepSeek-R1", parameters_b=32.0,
            min_ram_gb=24, recommended_ram_gb=48, min_vram_gb=20, recommended_vram_gb=24, disk_gb=20, quality_score=91,
            license="MIT", source_url="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", runtime="llama.cpp / Transformers"),
    AIModel("Qwen/Qwen3-32B", "Qwen3 32B Q4", "Qwen3", parameters_b=32.0, min_ram_gb=24, recommended_ram_gb=48,
            min_vram_gb=20, recommended_vram_gb=24, disk_gb=20, quality_score=90, license="Apache-2.0",
            source_url="https://huggingface.co/Qwen/Qwen3-32B"),
    AIModel("openai/gpt-oss-20b", "GPT-OSS 20B (MXFP4)", "GPT-OSS", parameters_b=21.0, min_ram_gb=16,
            recommended_ram_gb=32, min_vram_gb=12, recommended_vram_gb=16, disk_gb=13, quality_score=89,
            license="Apache-2.0", source_url="https://huggingface.co/openai/gpt-oss-20b", confidence="documentado"),
    AIModel("google/gemma-3-27b-it", "Gemma 3 27B IT Q4", "Gemma 3", parameters_b=27.0, min_ram_gb=20,
            recommended_ram_gb=40, min_vram_gb=16, recommended_vram_gb=24, disk_gb=17, quality_score=88,
            license="Gemma", gated=True, source_url="https://huggingface.co/google/gemma-3-27b-it"),
    AIModel("mistralai/Mistral-Small-3.1-24B-Instruct-2503", "Mistral Small 3.1 24B Q4", "Mistral", parameters_b=24.0,
            min_ram_gb=20, recommended_ram_gb=32, min_vram_gb=16, recommended_vram_gb=24, disk_gb=15, quality_score=87,
            license="Apache-2.0", source_url="https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503"),
    AIModel("Qwen/Qwen3-14B", "Qwen3 14B Q4", "Qwen3", parameters_b=14.0, min_ram_gb=12, recommended_ram_gb=24,
            min_vram_gb=9, recommended_vram_gb=12, disk_gb=9, quality_score=85, license="Apache-2.0",
            source_url="https://huggingface.co/Qwen/Qwen3-14B"),
    AIModel("microsoft/phi-4", "Phi-4 14B Q4", "Phi", parameters_b=14.0, min_ram_gb=12, recommended_ram_gb=24,
            min_vram_gb=9, recommended_vram_gb=12, disk_gb=9, quality_score=84, license="MIT",
            source_url="https://huggingface.co/microsoft/phi-4"),
    AIModel("google/gemma-3-12b-it", "Gemma 3 12B IT Q4", "Gemma 3", parameters_b=12.0, min_ram_gb=10,
            recommended_ram_gb=20, min_vram_gb=8, recommended_vram_gb=12, disk_gb=8, quality_score=83,
            license="Gemma", gated=True, source_url="https://huggingface.co/google/gemma-3-12b-it"),
    AIModel("Qwen/Qwen3-8B", "Qwen3 8B Q4", "Qwen3", parameters_b=8.0, min_ram_gb=8, recommended_ram_gb=16,
            min_vram_gb=6, recommended_vram_gb=8, disk_gb=5.5, quality_score=80, license="Apache-2.0",
            source_url="https://huggingface.co/Qwen/Qwen3-8B"),
    AIModel("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "DeepSeek R1 Distill Qwen 7B Q4", "DeepSeek-R1", parameters_b=7.6,
            min_ram_gb=8, recommended_ram_gb=16, min_vram_gb=5.5, recommended_vram_gb=8, disk_gb=5,
            quality_score=79, license="MIT", source_url="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"),
    AIModel("google/gemma-3-4b-it", "Gemma 3 4B IT Q4", "Gemma 3", parameters_b=4.0, min_ram_gb=6,
            recommended_ram_gb=12, min_vram_gb=3.5, recommended_vram_gb=6, disk_gb=3.2, quality_score=75,
            license="Gemma", gated=True, source_url="https://huggingface.co/google/gemma-3-4b-it"),
    AIModel("microsoft/Phi-4-mini-instruct", "Phi-4 Mini 3.8B Q4", "Phi", parameters_b=3.8, min_ram_gb=6,
            recommended_ram_gb=12, min_vram_gb=3, recommended_vram_gb=6, disk_gb=3, quality_score=74,
            license="MIT", source_url="https://huggingface.co/microsoft/Phi-4-mini-instruct"),
    AIModel("meta-llama/Llama-3.2-3B-Instruct", "Llama 3.2 3B Instruct Q4", "Llama", parameters_b=3.2, min_ram_gb=6,
            recommended_ram_gb=10, min_vram_gb=3, recommended_vram_gb=4, disk_gb=2.5, quality_score=71,
            license="Llama 3.2 Community", gated=True, source_url="https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct"),
    AIModel("Qwen/Qwen3-1.7B", "Qwen3 1.7B Q4", "Qwen3", parameters_b=1.7, min_ram_gb=4,
            recommended_ram_gb=8, min_vram_gb=2, recommended_vram_gb=3, disk_gb=1.5, quality_score=67,
            license="Apache-2.0", source_url="https://huggingface.co/Qwen/Qwen3-1.7B"),
    AIModel("google/gemma-3-1b-it", "Gemma 3 1B IT Q4", "Gemma 3", parameters_b=1.0, min_ram_gb=4,
            recommended_ram_gb=8, min_vram_gb=1.5, recommended_vram_gb=2, disk_gb=1.2, quality_score=61,
            license="Gemma", gated=True, source_url="https://huggingface.co/google/gemma-3-1b-it"),
    AIModel("Qwen/Qwen3-0.6B", "Qwen3 0.6B Q4", "Qwen3", parameters_b=0.6, min_ram_gb=3,
            recommended_ram_gb=6, min_vram_gb=1, recommended_vram_gb=2, disk_gb=0.8, quality_score=57,
            license="Apache-2.0", source_url="https://huggingface.co/Qwen/Qwen3-0.6B"),
    AIModel("provider/anthropic-claude", "Claude (serviço em nuvem)", "Claude", quality_score=98,
            source="provider", source_url="https://www.anthropic.com/claude", runtime="API / navegador", notes="Não é distribuído para execução local.", deployment="cloud", confidence="documentado"),
    AIModel("provider/openai-gpt", "GPT (serviço em nuvem)", "GPT", quality_score=98,
            source="provider", source_url="https://openai.com/", runtime="API / navegador", notes="Não é distribuído para execução local.", deployment="cloud", confidence="documentado"),
]

CURATED_ECOSYSTEM = [
    {"url": "https://github.com/ggml-org/llama.cpp", "name": "ggml-org/llama.cpp", "description": "Inferência de LLMs em C/C++ com CPU, GPU e quantização GGUF.", "platform": "GitHub", "license": "MIT", "topics": ["llm", "gguf", "inference"]},
    {"url": "https://github.com/ollama/ollama", "name": "ollama/ollama", "description": "Runtime e gerenciador simples para modelos locais.", "platform": "GitHub", "license": "MIT", "topics": ["local-ai", "llm"]},
    {"url": "https://github.com/huggingface/transformers", "name": "huggingface/transformers", "description": "Biblioteca de arquiteturas e pipelines de aprendizado de máquina.", "platform": "GitHub", "license": "Apache-2.0", "topics": ["transformers", "machine-learning"]},
    {"url": "https://github.com/vllm-project/vllm", "name": "vllm-project/vllm", "description": "Servidor de inferência de alto desempenho para LLMs.", "platform": "GitHub", "license": "Apache-2.0", "topics": ["serving", "llm"]},
    {"url": "https://github.com/ggerganov/whisper.cpp", "name": "ggerganov/whisper.cpp", "description": "Inferência local do Whisper para reconhecimento de fala.", "platform": "GitHub", "license": "MIT", "topics": ["speech", "inference"]},
]


class CatalogDB:
    def __init__(self, path: Path | None = None):
        self.path = path or (app_data_dir() / "catalog.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()
        self.seed()

    def _create_schema(self) -> None:
        columns = ",".join(f"{field.name} {self._sql_type(field.name)}" for field in fields(AIModel))
        self.connection.executescript(f"""
        CREATE TABLE IF NOT EXISTS models ({columns}, PRIMARY KEY(model_id, quantization_bits));
        CREATE INDEX IF NOT EXISTS idx_models_quality ON models(quality_score DESC);
        CREATE INDEX IF NOT EXISTS idx_models_task ON models(task);
        CREATE INDEX IF NOT EXISTS idx_models_source ON models(source);
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ecosystem (
            url TEXT PRIMARY KEY, name TEXT, description TEXT, platform TEXT, stars INTEGER,
            license TEXT, updated_at TEXT, topics TEXT
        );
        """)
        self.connection.commit()

    @staticmethod
    def _sql_type(name: str) -> str:
        if name in {"parameters_b", "min_ram_gb", "recommended_ram_gb", "min_vram_gb", "recommended_vram_gb", "disk_gb", "quality_score", "popularity_score"}:
            return "REAL"
        if name in {"quantization_bits", "context_length", "gated"}:
            return "INTEGER"
        return "TEXT"

    def seed(self) -> None:
        if self.get_meta("seed_version") == "2":
            return
        self.upsert_models(CURATED_MODELS)
        self.upsert_ecosystem(CURATED_ECOSYSTEM)
        self.set_meta("seed_version", "2")

    def upsert_models(self, models: Iterable[AIModel]) -> int:
        names = [f.name for f in fields(AIModel)]
        assignments = ",".join(f"{name}=excluded.{name}" for name in names if name not in {"model_id", "quantization_bits"})
        sql = (f"INSERT INTO models ({','.join(names)}) VALUES ({','.join('?' for _ in names)}) "
               f"ON CONFLICT(model_id,quantization_bits) DO UPDATE SET {assignments} "
               "WHERE models.source NOT IN ('curated','provider')")
        rows = [[getattr(model, name) for name in names] for model in models]
        if not rows:
            return 0
        self.connection.executemany(sql, rows)
        self.connection.commit()
        return len(rows)

    def list_models(self, *, query: str = "", task: str = "", local_only: bool = True,
                    known_requirements_only: bool = False, limit: int = 1000) -> list[AIModel]:
        where: list[str] = []
        values: list[Any] = []
        if query:
            where.append("(display_name LIKE ? OR model_id LIKE ? OR family LIKE ?)")
            values.extend([f"%{query}%"] * 3)
        if task:
            where.append("task = ?")
            values.append(task)
        if local_only:
            where.append("deployment = 'local'")
        if known_requirements_only:
            where.append("parameters_b > 0 AND min_ram_gb > 0")
        condition = " WHERE " + " AND ".join(where) if where else ""
        values.append(max(1, limit))
        rows = self.connection.execute(
            f"SELECT * FROM models{condition} ORDER BY quality_score DESC, popularity_score DESC, parameters_b DESC LIMIT ?", values
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_model(self, model_id: str) -> AIModel | None:
        row = self.connection.execute(
            "SELECT * FROM models WHERE model_id=? ORDER BY quality_score DESC, quantization_bits ASC LIMIT 1", (model_id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> AIModel:
        values = dict(row)
        values["gated"] = bool(values["gated"])
        return AIModel(**values)

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM models").fetchone()[0])

    def tasks(self) -> list[str]:
        return [str(row[0]) for row in self.connection.execute("SELECT DISTINCT task FROM models WHERE task != '' ORDER BY task")]

    def set_meta(self, key: str, value: str) -> None:
        self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (key, value))
        self.connection.commit()

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else default

    def upsert_ecosystem(self, items: list[dict[str, Any]]) -> None:
        self.connection.executemany(
            "INSERT OR REPLACE INTO ecosystem(url,name,description,platform,stars,license,updated_at,topics) VALUES(?,?,?,?,?,?,?,?)",
            [(x["url"], x["name"], x.get("description", ""), x.get("platform", "GitHub"), x.get("stars", 0),
              x.get("license", "Desconhecida"), x.get("updated_at", ""), json.dumps(x.get("topics", []))) for x in items],
        )
        self.connection.commit()

    def list_ecosystem(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM ecosystem ORDER BY stars DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.connection.close()


def _estimate_parameters(item: dict[str, Any]) -> float:
    safetensors = item.get("safetensors") or {}
    total = safe_float(safetensors.get("total"))
    if total:
        return total / 1e9
    config = item.get("config") or {}
    for key in ("num_parameters", "n_parameters", "parameter_count"):
        value = safe_float(config.get(key))
        if value:
            return value / 1e9 if value > 1000 else value
    text = f"{item.get('id', '')} {' '.join(item.get('tags') or [])}"
    matches = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])", text)
    plausible = [safe_float(m) for m in matches if 0.05 <= safe_float(m) <= 2000]
    return min(plausible) if plausible else 0.0


def _quantization_bits(item: dict[str, Any]) -> int:
    text = " ".join([item.get("id", ""), *(item.get("tags") or [])]).lower()
    if any(term in text for term in ("q2_", "2bit", "int2")):
        return 2
    if any(term in text for term in ("q3_", "3bit", "int3")):
        return 3
    if any(term in text for term in ("q4_", "4bit", "int4", "gptq", "awq", "mxfp4", "gguf")):
        return 4
    if any(term in text for term in ("q5_", "5bit", "int5")):
        return 5
    if any(term in text for term in ("q6_", "6bit", "int6")):
        return 6
    if any(term in text for term in ("q8_", "8bit", "int8")):
        return 8
    return 16


def _requirements(parameters_b: float, bits: int, task: str) -> tuple[float, float, float, float, float]:
    if parameters_b <= 0:
        return 0, 0, 0, 0, 0
    weight_gb = parameters_b * bits / 8 * 1.08
    task_factor = 1.25 if task in {"text-generation", "image-text-to-text", "text2text-generation"} else 1.12
    min_ram = max(3.0, math.ceil(weight_gb * task_factor + 2))
    rec_ram = max(min_ram, math.ceil(weight_gb * 1.6 + 4))
    min_vram = max(1.0, math.ceil(weight_gb * 0.9))
    rec_vram = max(min_vram, math.ceil(weight_gb * 1.15 + 1))
    return min_ram, rec_ram, min_vram, rec_vram, math.ceil(weight_gb * 1.12 * 10) / 10


def hf_item_to_model(item: dict[str, Any]) -> AIModel:
    model_id = str(item.get("id") or item.get("modelId") or "modelo-sem-id")
    tags = item.get("tags") or []
    task = item.get("pipeline_tag") or "unknown"
    params = _estimate_parameters(item)
    bits = _quantization_bits(item)
    min_ram, rec_ram, min_vram, rec_vram, disk = _requirements(params, bits, task)
    license_name = next((str(tag).split(":", 1)[1] for tag in tags if str(tag).startswith("license:")), "Desconhecida")
    downloads = safe_int(item.get("downloads"))
    likes = safe_int(item.get("likes"))
    popularity = min(100.0, math.log10(max(downloads, 1)) * 12 + math.log10(max(likes, 1)) * 6)
    config = item.get("config") or {}
    context = safe_int(config.get("max_position_embeddings") or config.get("n_positions"))
    family = model_id.split("/", 1)[-1].split("-")[0]
    quality = round(popularity * 0.55 + min(25, math.log2(max(params, 0.25)) * 3 + 7), 2)
    return AIModel(
        model_id=model_id, display_name=model_id.split("/", 1)[-1], family=family, task=task,
        parameters_b=round(params, 3), quantization_bits=bits, min_ram_gb=min_ram, recommended_ram_gb=rec_ram,
        min_vram_gb=min_vram, recommended_vram_gb=rec_vram, disk_gb=disk, context_length=context,
        quality_score=quality, popularity_score=round(popularity, 2), license=license_name,
        gated=bool(item.get("gated")), source="Hugging Face", source_url=f"https://huggingface.co/{model_id}",
        updated_at=str(item.get("lastModified") or ""), runtime="Transformers / runtime compatível",
        notes="Requisitos inferidos de parâmetros, precisão e metadados públicos.", confidence="estimado" if params else "metadados insuficientes",
    )


class OnlineCatalogSync:
    def __init__(self, database: CatalogDB):
        self.database = database

    @staticmethod
    def _get_json(url: str, token: str = "", timeout: int = 30) -> tuple[Any, str]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, response.headers.get("Link", "")

    def sync_huggingface(self, *, limit: int | None = 500, token: str = "", progress: Progress | None = None) -> int:
        properties = ["safetensors", "config", "downloads", "likes", "lastModified", "createdAt",
                      "gated", "pipeline_tag", "tags", "library_name", "author"]
        query = urllib.parse.urlencode({
            "sort": "lastModified", "direction": "-1", "limit": "100", "expand": properties,
        }, doseq=True)
        base = "https://huggingface.co/api/models?" + query
        url = base
        total = 0
        while url and (limit is None or total < limit):
            page, link = self._get_json(url, token)
            if not isinstance(page, list):
                break
            if limit is not None:
                page = page[: max(0, limit - total)]
            models = [hf_item_to_model(item) for item in page]
            self.database.upsert_models(models)
            total += len(models)
            if progress:
                progress(total, f"Hugging Face: {total:,} modelos indexados")
            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            url = match.group(1) if match else ""
            if not page:
                break
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.database.set_meta("hf_last_sync", stamp)
        self.database.set_meta("hf_last_sync_count", str(total))
        return total

    def sync_github(self, *, token: str = "", limit: int = 100, progress: Progress | None = None) -> int:
        # GitHub não aceita OR entre qualificadores de tópico neste endpoint.
        query = urllib.parse.quote("topic:large-language-model")
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page={min(limit, 100)}"
        headers_token = token
        payload, _ = self._get_json(url, headers_token)
        results: list[dict[str, Any]] = []
        for item in (payload.get("items") if isinstance(payload, dict) else []) or []:
            license_data = item.get("license") or {}
            results.append({
                "url": item.get("html_url", ""), "name": item.get("full_name", ""),
                "description": item.get("description") or "", "platform": "GitHub",
                "stars": safe_int(item.get("stargazers_count")), "license": license_data.get("spdx_id") or "Desconhecida",
                "updated_at": item.get("updated_at") or "", "topics": item.get("topics") or [],
            })
        self.database.upsert_ecosystem(results)
        self.database.set_meta("github_last_sync", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        if progress:
            progress(len(results), f"GitHub: {len(results)} projetos de ecossistema indexados")
        return len(results)


def describe_sync_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        if error.code in {401, 403, 429}:
            return f"A fonte limitou as consultas (HTTP {error.code}). Tente mais tarde ou informe um token nas configurações."
        return f"A fonte respondeu com HTTP {error.code}."
    if isinstance(error, urllib.error.URLError):
        return f"Sem acesso à fonte: {error.reason}"
    return str(error)
