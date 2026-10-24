# Contribuindo com o Bercha LivreNexo

Obrigado pelo interesse em melhorar um projeto de software livre. São bem-vindas
correções, novos detectores, conectores públicos, traduções, melhorias de
acessibilidade e benchmarks reproduzíveis.

## Antes de começar

1. Consulte as issues existentes.
2. Para mudanças grandes, abra uma proposta antes da implementação.
3. Não inclua credenciais, dados pessoais, modelos proprietários ou conteúdo sem
   licença compatível.
4. Respeite o [Código de Conduta](CODE_OF_CONDUCT.md).

## Ambiente de desenvolvimento

```bash
python -m venv .venv
pip install -e ".[dev,pdf,enhanced]"
pytest -q
```

## Pull requests

- mantenha cada PR focado em um objetivo;
- inclua testes para comportamento novo ou corrigido;
- atualize documentação e changelog quando necessário;
- descreva impacto, decisões e limitações;
- confirme que `pytest -q` passa em seu ambiente.

Contribuições são aceitas sob a mesma licença GPL-3.0-or-later do projeto.
