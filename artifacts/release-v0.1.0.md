# Bercha LivreNexo 0.1.0

Primeira versão pública do nexo livre entre seu hardware e a inteligência
artificial local.

## Destaques

- interface gráfica em português com 14 áreas de análise;
- inventário de CPU, placa-mãe, BIOS, RAM, SPD, GPU, VRAM e discos;
- suporte de código-fonte a Windows, Linux e macOS;
- catálogo SQLite e sincronização pública com Hugging Face e GitHub;
- ranking BerchaScore e parecer de compatibilidade explicável;
- montador completo de PC para o modelo escolhido;
- relatórios HTML, TXT, JSON e PDF;
- CLI para automação e executável Windows portátil;
- licença GNU GPL-3.0-or-later, sem telemetria e sem links afiliados.

## Download para Windows

Baixe `Bercha-LivreNexo-v0.1.0-Windows-x64.exe`. O arquivo é portátil e não
exige Python. Como este primeiro binário ainda não possui assinatura comercial,
o Windows SmartScreen pode solicitar confirmação na primeira execução.

Verifique a integridade com o arquivo `SHA256SUMS.txt` ou com:

```powershell
Get-FileHash .\Bercha-LivreNexo-v0.1.0-Windows-x64.exe -Algorithm SHA256
```

SHA-256 esperado:
`2a3aa8c504859ac83ec5c19a5a724d59dbca9c4cff8f875b759dc7459c2cb706`

## Validação

- 10 testes automatizados aprovados;
- CI aprovada em Windows, Ubuntu e macOS;
- Python 3.10 e 3.13 validados;
- executável iniciado e encerrado sem processos residuais.

Consulte o README, a metodologia e a política de segurança antes de usar as
estimativas para aquisição de hardware.
