from __future__ import annotations

import math
import urllib.parse

from .models import AIModel, BuildRecommendation, ComponentRecommendation, HardwareReport


SHOPS = {
    "KaBuM!": "https://www.kabum.com.br/busca/",
    "Pichau": "https://www.pichau.com.br/search?q=",
    "Amazon Brasil": "https://www.amazon.com.br/s?k=",
    "Mercado Livre": "https://lista.mercadolivre.com.br/",
}


def shopping_links(query: str) -> dict[str, str]:
    encoded = urllib.parse.quote_plus(query)
    slugged = urllib.parse.quote(query.replace(" ", "-"), safe="")
    return {
        "KaBuM!": SHOPS["KaBuM!"] + encoded,
        "Pichau": SHOPS["Pichau"] + encoded,
        "Amazon Brasil": SHOPS["Amazon Brasil"] + encoded,
        "Mercado Livre": SHOPS["Mercado Livre"] + slugged,
    }


def _component(category: str, product: str, specification: str, reason: str,
               price: tuple[int, int], required: bool = True) -> ComponentRecommendation:
    return ComponentRecommendation(category, product, specification, reason, price, shopping_links(product), required)


class PCBuilder:
    def build(self, model: AIModel, hardware: HardwareReport | None = None, tier: str = "recomendado") -> BuildRecommendation:
        if model.deployment != "local":
            return BuildRecommendation(model, tier, [], (0, 0), ["Este modelo é um serviço remoto e não pode ser instalado localmente."])
        target_vram = max(model.recommended_vram_gb, model.min_vram_gb)
        target_ram = max(16, int(math.ceil(model.recommended_ram_gb / 16) * 16))
        target_disk = max(1000, int(math.ceil((model.disk_gb * 5 + 250) / 500) * 500))
        components: list[ComponentRecommendation] = []

        if target_vram <= 8:
            gpu = ("GPU NVIDIA GeForce RTX com 8–12 GB", "mínimo 8 GB VRAM; CUDA", (1800, 3500))
            cpu = ("AMD Ryzen 5 7600 ou Intel Core i5 equivalente", "6+ núcleos modernos, AVX2", (1100, 1800))
            psu = ("Fonte 650 W 80 Plus Gold", "ATX 3.x, proteções elétricas completas", (450, 750))
        elif target_vram <= 16:
            gpu = ("GPU NVIDIA GeForce RTX com 16 GB", "16 GB VRAM; CUDA; barramento PCIe x16", (3500, 7500))
            cpu = ("AMD Ryzen 7 9700X ou Intel Core Ultra 7 equivalente", "8+ núcleos modernos, AVX2", (2200, 3500))
            psu = ("Fonte 850 W 80 Plus Gold", "ATX 3.x e conector nativo da GPU", (700, 1200))
        elif target_vram <= 24:
            gpu = ("GPU NVIDIA GeForce RTX com 24–32 GB", "mínimo 24 GB VRAM; CUDA", (9000, 22000))
            cpu = ("AMD Ryzen 9 9950X ou Intel Core Ultra 9 equivalente", "16 núcleos recomendados", (4000, 6000))
            psu = ("Fonte 1200 W 80 Plus Gold/Platinum", "ATX 3.x, potência contínua e folga térmica", (1200, 2200))
        elif target_vram <= 48:
            gpu = ("GPU profissional NVIDIA com 48 GB", "48 GB ECC recomendados; suporte CUDA", (35000, 70000))
            cpu = ("AMD Threadripper 7960X ou workstation equivalente", "24+ núcleos e muitas linhas PCIe", (10000, 18000))
            psu = ("Fonte 1600 W 80 Plus Platinum", "circuito elétrico dedicado recomendado", (2200, 3800))
        else:
            gpu_count = max(2, math.ceil(target_vram / 48))
            gpu = (f"{gpu_count} GPUs profissionais NVIDIA de 48 GB", f"VRAM agregada >= {target_vram:.0f} GB; runtime com tensor parallel", (gpu_count * 35000, gpu_count * 70000))
            cpu = ("AMD Threadripper Pro 7975WX ou servidor equivalente", "32+ núcleos, ECC e linhas PCIe para multi-GPU", (18000, 35000))
            psu = ("Fonte(s) redundante(s) de classe workstation/servidor", "dimensionar por TDP total + 30%; instalação elétrica dedicada", (4000, 9000))

        components.append(_component("GPU", gpu[0], gpu[1], "É o componente dominante para inferência local e define o tamanho do modelo/contexto.", gpu[2]))
        components.append(_component("Processador", cpu[0], cpu[1], "Alimenta a GPU, prepara prompts e permite offload para CPU.", cpu[2]))

        workstation = target_vram > 24
        board_name = "Placa-mãe workstation compatível com o processador" if workstation else "Placa-mãe compatível, 4 slots de RAM e PCIe x16"
        board_spec = "ECC, múltiplos slots PCIe x16 físicos e espaçamento para GPU" if workstation else "UEFI atualizada, 2+ slots M.2, rede 2.5 GbE"
        components.append(_component("Placa-mãe", board_name, board_spec, "Compatibilidade elétrica/mecânica e possibilidade de expansão.", (3500, 9000) if workstation else (900, 2200)))
        memory_kind = "ECC DDR5" if workstation else "DDR5 em kit pareado"
        components.append(_component("Memória RAM", f"{target_ram} GB {memory_kind}", f"{target_ram} GB ou mais; prefira 2 módulos quando possível", "Mantém pesos, KV cache e o sistema sem paginação excessiva.", (target_ram * 35, target_ram * 65)))
        components.append(_component("Armazenamento", f"SSD NVMe {target_disk // 1000 if target_disk >= 1000 else target_disk} {'TB' if target_disk >= 1000 else 'GB'}", "NVMe TLC, boa durabilidade e dissipador", "Modelos, quantizações e cache ocupam várias vezes o peso de uma única cópia.", (500, 2200) if target_disk <= 2000 else (1800, 5000)))
        components.append(_component("Fonte", psu[0], psu[1], "Evita instabilidade sob carga sustentada de IA.", psu[2]))
        cooler_product = "Water cooler 360 mm ou solução workstation" if workstation or target_vram > 16 else "Cooler torre dual-fan de alto desempenho"
        components.append(_component("Cooler", cooler_product, "Compatível com socket e TDP do processador", "Inferência prolongada mantém CPU/GPU em carga contínua.", (350, 1600)))
        case_product = "Gabinete full tower/workstation para multi-GPU" if workstation else "Gabinete airflow mid/full tower"
        components.append(_component("Gabinete", case_product, "Frente ventilada, filtros e folga para comprimento/espessura da GPU", "Temperatura e espaço físico determinam estabilidade e ruído.", (400, 1800)))
        ups_va = 3000 if workstation else 1500 if target_vram > 16 else 1200
        components.append(_component("Nobreak/UPS", f"Nobreak senoidal online {ups_va} VA", "Saída senoidal; potência em watts superior ao consumo real", "Protege o trabalho e permite desligamento seguro; confirme compatibilidade com PFC ativo.", (1200, 6000), required=False))
        components.append(_component("Ventilação", "Kit de ventoinhas PWM de alta pressão/fluxo", "Entrada frontal/inferior e exaustão traseira/superior", "Remove o calor gerado em cargas longas.", (150, 700)))

        total_min = sum(c.estimated_price_brl[0] for c in components if c.required)
        total_max = sum(c.estimated_price_brl[1] for c in components if c.required)
        caveats = [
            "Faixas de preço são apenas referências offline em BRL, sem frete; os links abrem buscas sem afiliação.",
            "Confirme socket, QVL da memória, dimensões da GPU, conectores da fonte e limites elétricos antes de comprar.",
            "VRAM de várias GPUs não se soma automaticamente; o runtime e o modelo precisam suportar paralelismo/offload.",
            "Uma loja ou integrador deve validar BIOS, refrigeração, circuito elétrico e montagem final.",
        ]
        if hardware:
            caveats.append("A lista é uma configuração-alvo completa; peças atuais reutilizáveis exigem validação física que o software não consegue fazer sozinho.")
        return BuildRecommendation(model, tier, components, (total_min, total_max), caveats)


REFERENCE_LINKS = {
    "Hugging Face – estimador de memória": "https://huggingface.co/docs/accelerate/usage_guides/model_size_estimator",
    "llama.cpp – execução e quantização": "https://github.com/ggml-org/llama.cpp",
    "PCI-SIG – especificações PCI Express": "https://pcisig.com/specifications",
    "80 PLUS – eficiência de fontes": "https://www.clearesult.com/80plus/",
}
