# Metodologia do Bercha LivreNexo

## O que é medido e o que é estimado

O inventário de CPU, placa-mãe, BIOS, RAM, GPU, VRAM e armazenamento é lido do
sistema operacional. Fonte, cooler e gabinete não têm uma interface universal
de telemetria; por isso aparecem como não detectáveis. A VRAM de GPUs NVIDIA é
refinada com `nvidia-smi` quando disponível.

Os requisitos de um modelo sincronizado são estimados por:

```text
pesos_GB = parâmetros × bits / 8 × 1,08
RAM_mínima = pesos × fator_da_tarefa + 2 GB
RAM_recomendada = pesos × 1,60 + 4 GB
VRAM_mínima = pesos × 0,90
VRAM_recomendada = pesos × 1,15 + 1 GB
disco = pesos × 1,12
```

As margens cobrem aproximadamente runtime, buffers e KV cache, mas o contexto,
o lote, a arquitetura, o backend e a quantização mudam o consumo real. Modelos
sem contagem de parâmetros permanecem no catálogo com “dados insuficientes”.

## BerchaScore

O BerchaScore não é apresentado como verdade científica. Na lista curada ele é
uma nota editorial inicial. Nos registros sincronizados, é um índice de
descoberta calculado a partir de downloads, likes e escala do modelo. O ranking
ordena qualidade primeiro e mostra a compatibilidade separadamente — assim um
modelo avançado não desaparece só porque o computador atual é insuficiente.

Uma edição futura pode importar resultados reproduzíveis de Open LLM Leaderboard,
LM Evaluation Harness ou um conjunto de avaliações próprio. Resultados de tarefas
diferentes não devem ser comparados como se fossem a mesma métrica.

## Cobertura das fontes

- A sincronização rápida busca os 500 modelos públicos mais recentemente alterados
  no Hugging Face.
- A varredura completa segue a paginação pública até o fim e grava cada página em
  SQLite. Modelos privados, removidos ou invisíveis à conta não podem ser indexados.
- O GitHub é usado para descobrir o ecossistema de runtimes e projetos, não para
  inventar requisitos ausentes. Consultas anônimas têm limite de taxa.
- Tokens opcionais são lidos de `HF_TOKEN` e `GITHUB_TOKEN`; não são gravados nem
  incluídos em relatórios.

## Parecer de compatibilidade

- **Excelente:** VRAM recomendada e disco atendidos.
- **Compatível:** VRAM mínima e disco atendidos.
- **Compatível, lento:** RAM recomendada permite CPU/offload.
- **Limítrofe:** somente RAM mínima; há risco de paginação ou falha em contexto longo.
- **Incompatível:** memória ou disco abaixo do mínimo.
- **Nuvem/API:** o modelo não é distribuído para execução local.

Tokens por segundo são sempre exibidos como faixa heurística larga. O benchmark da
aba Bench mede apenas um kernel numérico interno e não é convertido em tokens/s.
