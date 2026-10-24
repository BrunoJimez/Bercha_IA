from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .builder import PCBuilder
from .catalog import CatalogDB, OnlineCatalogSync, describe_sync_error
from .hardware import HardwareScanner, quick_benchmark
from .recommender import CompatibilityEngine
from .reports import export_report, report_payload


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _progress(count: int, message: str) -> None:
    print(f"\r{message}", end="", file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bercha-livrenexo", description="Análise livre de hardware, modelos de IA e configurações locais.")
    parser.add_argument("--version", action="version", version=f"Bercha LivreNexo {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="Abrir a interface gráfica")
    sub.add_parser("scan", help="Inventariar o hardware em JSON")

    models = sub.add_parser("models", help="Listar o catálogo local")
    models.add_argument("--search", default="")
    models.add_argument("--limit", type=int, default=50)
    models.add_argument("--all", action="store_true", help="Incluir nuvem e requisitos desconhecidos")

    recommend = sub.add_parser("recommend", help="Recomendar modelos para este PC")
    recommend.add_argument("--limit", type=int, default=20)
    recommend.add_argument("--include-incompatible", action="store_true")

    sync = sub.add_parser("sync", help="Sincronizar Hugging Face e projetos GitHub")
    sync.add_argument("--all", action="store_true", help="Percorrer todo o catálogo do Hugging Face (pode demorar)")
    sync.add_argument("--limit", type=int, default=500, help="Quantidade no modo rápido")
    sync.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    sync.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    sync.add_argument("--skip-github", action="store_true")

    build = sub.add_parser("build", help="Montar um PC para um modelo")
    build.add_argument("model_id")

    report = sub.add_parser("report", help="Gerar relatório .html, .txt, .json ou .pdf")
    report.add_argument("output", type=Path)
    report.add_argument("--model-id", default="", help="Incluir uma configuração de PC para este modelo")
    report.add_argument("--limit", type=int, default=30)
    report.add_argument("--include-serials", action="store_true")

    bench = sub.add_parser("bench", help="Rodar microbenchmark interno")
    bench.add_argument("--seconds", type=float, default=0.7)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command or args.command == "gui":
        try:
            from .gui import main as gui_main
            gui_main()
            return 0
        except (ImportError, RuntimeError) as exc:
            print(f"Não foi possível abrir a interface: {exc}", file=sys.stderr)
            return 2
    if args.command == "scan":
        print(_json(HardwareScanner().scan().to_dict()))
        return 0
    if args.command == "bench":
        print(_json(quick_benchmark(max(0.1, min(args.seconds, 10)))))
        return 0

    database = CatalogDB()
    try:
        if args.command == "models":
            models = database.list_models(query=args.search, local_only=not args.all,
                                          known_requirements_only=not args.all, limit=args.limit)
            print(_json([model.to_dict() for model in models]))
            return 0
        if args.command == "sync":
            syncer = OnlineCatalogSync(database)
            hf_count = gh_count = 0
            warnings: list[str] = []
            try:
                hf_count = syncer.sync_huggingface(limit=None if args.all else args.limit, token=args.hf_token, progress=_progress)
            except Exception as exc:  # mensagem pública sem trace/segredos
                warnings.append("Hugging Face: " + describe_sync_error(exc))
            if not args.skip_github:
                try:
                    gh_count = syncer.sync_github(token=args.github_token, progress=_progress)
                except Exception as exc:
                    warnings.append("GitHub: " + describe_sync_error(exc))
            print(file=sys.stderr)
            for warning in warnings:
                print(warning, file=sys.stderr)
            print(_json({"huggingface": hf_count, "github": gh_count, "catalog_total": database.count(), "warnings": warnings}))
            return 1 if hf_count == 0 and gh_count == 0 else 0
        hardware = HardwareScanner().scan()
        engine = CompatibilityEngine()
        models = database.list_models(local_only=True, known_requirements_only=True, limit=3000)
        results = engine.rank(hardware, models, include_incompatible=True)
        if args.command == "recommend":
            if not args.include_incompatible:
                results = [r for r in results if r.status != "Incompatível"]
            print(_json([result.to_dict() for result in results[:args.limit]]))
            return 0
        if args.command == "build":
            model = database.get_model(args.model_id)
            if not model:
                print(f"Modelo não encontrado: {args.model_id}", file=sys.stderr)
                return 2
            print(_json(PCBuilder().build(model, hardware).to_dict()))
            return 0
        if args.command == "report":
            build_data = None
            if args.model_id:
                model = database.get_model(args.model_id)
                if not model:
                    print(f"Modelo não encontrado: {args.model_id}", file=sys.stderr)
                    return 2
                build_data = PCBuilder().build(model, hardware)
            payload = report_payload(hardware, results[:args.limit], build_data, args.include_serials)
            export_report(args.output.resolve(), payload)
            print(str(args.output.resolve()))
            return 0
    finally:
        database.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
