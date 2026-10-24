from __future__ import annotations

import math

from .models import AIModel, CompatibilityResult, HardwareReport


LOCAL_TASKS = {
    "text-generation", "text2text-generation", "image-text-to-text", "automatic-speech-recognition",
    "text-to-image", "image-classification", "text-classification", "feature-extraction", "unknown",
}


class CompatibilityEngine:
    """Heurística explicável; nunca transforma estimativa em medição."""

    def evaluate(self, hardware: HardwareReport, model: AIModel) -> CompatibilityResult:
        if model.deployment == "cloud":
            return CompatibilityResult(
                model=model, status="Nuvem/API", score=100, mode="Remoto",
                reasons=["O processamento ocorre no provedor; o PC executa apenas o cliente."],
                bottlenecks=["Requer internet, conta no provedor e pode ter custo/limites de uso."],
                estimated_tokens_per_second="Definido pelo provedor",
            )
        if model.parameters_b <= 0 or model.min_ram_gb <= 0:
            return CompatibilityResult(
                model=model, status="Dados insuficientes", score=0, mode="Indeterminado",
                reasons=["O repositório não publica parâmetros suficientes para estimar memória."],
                bottlenecks=["Abra o model card e confirme arquitetura, precisão e runtime."],
                estimated_tokens_per_second="Não estimável",
            )

        ram = hardware.system.total_ram_gb
        vram = hardware.best_vram_gb
        disk = hardware.total_storage_free_gb
        reasons: list[str] = []
        bottlenecks: list[str] = []
        score = 0.0

        ram_ratio = ram / max(model.recommended_ram_gb, 0.1)
        vram_ratio = vram / max(model.recommended_vram_gb, 0.1)
        disk_ratio = disk / max(model.disk_gb, 0.1)
        if vram >= model.recommended_vram_gb:
            mode = "GPU"
            status = "Excelente"
            score = 92
            reasons.append(f"VRAM ({vram:.1f} GB) alcança a recomendação ({model.recommended_vram_gb:.1f} GB).")
        elif vram >= model.min_vram_gb:
            mode = "GPU"
            status = "Compatível"
            score = 78
            reasons.append(f"VRAM ({vram:.1f} GB) atende ao mínimo ({model.min_vram_gb:.1f} GB).")
            bottlenecks.append("Contextos longos e lotes maiores podem exceder a VRAM.")
        elif ram >= model.recommended_ram_gb:
            mode = "CPU/híbrido"
            status = "Compatível, lento"
            score = 58
            reasons.append(f"A RAM ({ram:.1f} GB) permite CPU ou offload parcial para a GPU.")
            bottlenecks.append(f"Faltam aproximadamente {max(0, model.min_vram_gb - vram):.1f} GB de VRAM para o mínimo em GPU.")
        elif ram >= model.min_ram_gb:
            mode = "CPU"
            status = "Limítrofe"
            score = 40
            reasons.append(f"A RAM ({ram:.1f} GB) atende apenas ao mínimo estimado ({model.min_ram_gb:.1f} GB).")
            bottlenecks.append("O sistema pode paginar memória, ficar lento ou encerrar a inferência em contextos grandes.")
        else:
            mode = "Não recomendado"
            status = "Incompatível"
            score = 10
            bottlenecks.append(f"RAM: faltam aproximadamente {max(0, model.min_ram_gb - ram):.1f} GB para o mínimo.")
            if vram < model.min_vram_gb:
                bottlenecks.append(f"VRAM: faltam aproximadamente {model.min_vram_gb - vram:.1f} GB para execução em GPU.")

        if disk < model.disk_gb:
            bottlenecks.append(f"Armazenamento livre insuficiente: {disk:.1f} GB disponível para {model.disk_gb:.1f} GB estimados.")
            score -= 25
            if status not in {"Incompatível", "Dados insuficientes"}:
                status = "Incompatível"
                mode = "Sem espaço"
        else:
            reasons.append(f"Espaço livre ({disk:.1f} GB) comporta os pesos estimados ({model.disk_gb:.1f} GB).")

        if not any(x in hardware.cpu.instruction_sets for x in ("AVX2", "AVX512F", "NEON", "ASIMD")):
            bottlenecks.append("AVX2/NEON não foi confirmado; runtimes de CPU podem usar kernels mais lentos ou incompatíveis.")
            score -= 5
        if model.gated:
            bottlenecks.append("Modelo com acesso controlado: aceite a licença/autentique-se antes de baixar.")
        score += min(5, max(0, ram_ratio - 1) * 3) + min(3, max(0, vram_ratio - 1) * 2)
        return CompatibilityResult(
            model=model, status=status, score=round(max(0, min(100, score)), 1), mode=mode,
            reasons=reasons, bottlenecks=bottlenecks,
            estimated_tokens_per_second=self._speed_band(hardware, model, mode),
        )

    @staticmethod
    def _speed_band(hardware: HardwareReport, model: AIModel, mode: str) -> str:
        if model.task not in {"text-generation", "text2text-generation", "image-text-to-text", "unknown"}:
            return "Não se aplica a tokens/s"
        if mode == "GPU":
            # Faixa deliberadamente larga: arquitetura, runtime e contexto mudam muito o resultado.
            ratio = max(0.15, hardware.best_vram_gb / max(model.parameters_b, 0.2))
            low = max(1, int(6 * ratio))
            high = max(low + 1, int(28 * ratio))
            return f"~{low}–{min(high, 180)} tokens/s (faixa heurística)"
        if mode in {"CPU", "CPU/híbrido"}:
            core_factor = max(1, hardware.cpu.physical_cores or hardware.cpu.logical_cores // 2)
            estimate = core_factor / max(model.parameters_b, 0.5) * (2.2 if mode == "CPU/híbrido" else 1.3)
            low = max(0.2, estimate * 0.45)
            high = max(low + 0.2, estimate * 1.8)
            return f"~{low:.1f}–{high:.1f} tokens/s (faixa heurística)"
        return "Não executável com segurança"

    def rank(self, hardware: HardwareReport, models: list[AIModel], include_incompatible: bool = True) -> list[CompatibilityResult]:
        results = [self.evaluate(hardware, model) for model in models]
        if not include_incompatible:
            results = [r for r in results if r.status not in {"Incompatível", "Dados insuficientes"}]
        # O pedido é qualidade do modelo primeiro; compatibilidade desempata e fica visível.
        return sorted(results, key=lambda r: (r.model.quality_score, r.score, r.model.popularity_score), reverse=True)


def formula_notes() -> list[str]:
    return [
        "Pesos ≈ parâmetros × bits/8 × 1,08; RAM e VRAM acrescentam margem para runtime, KV cache e sistema.",
        "BerchaScore mistura uma nota editorial nos modelos curados e popularidade/metadados nos modelos sincronizados.",
        "Tokens/s é uma faixa heurística, não um benchmark; confirme no runtime e na quantização escolhidos.",
        "Modelos com parâmetros desconhecidos são mostrados, mas não recebem um parecer de compatibilidade.",
    ]
