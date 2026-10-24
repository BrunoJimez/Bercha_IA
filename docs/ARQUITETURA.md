# Arquitetura

```text
GUI Tk / CLI
   ├── HardwareScanner ── CIM | /proc + sysfs | system_profiler | nvidia-smi
   ├── CatalogDB ──────── SQLite + base curada offline
   │      └── OnlineCatalogSync ── Hugging Face API + GitHub REST API
   ├── CompatibilityEngine ── parecer, gargalos e ranking explicável
   ├── PCBuilder ───────────── configuração-alvo + pesquisas em lojas
   └── Reports ─────────────── HTML | TXT | JSON | PDF opcional
```

O núcleo não depende da interface. Cada dataclass pode ser serializada, a CLI usa
os mesmos motores da GUI e o catálogo é gravado na pasta de dados local do usuário.
Não há servidor, conta própria, telemetria ou chave embutida.
