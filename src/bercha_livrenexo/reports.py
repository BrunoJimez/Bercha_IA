from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .builder import REFERENCE_LINKS
from .models import BuildRecommendation, CompatibilityResult, HardwareReport
from .recommender import formula_notes


def _redact(value: str) -> str:
    if not value:
        return value
    return ("•" * max(0, len(value) - 4)) + value[-4:]


def report_payload(hardware: HardwareReport, results: list[CompatibilityResult],
                   build: BuildRecommendation | None = None, include_serials: bool = False) -> dict[str, Any]:
    data = hardware.to_dict()
    if not include_serials:
        data["mainboard"]["serial"] = _redact(data["mainboard"].get("serial", ""))
        for module in data["memory_modules"]:
            module["serial"] = _redact(module.get("serial", ""))
    return {
        "application": "Bercha LivreNexo", "schema_version": 1, "hardware": data,
        "recommendations": [result.to_dict() for result in results],
        "build": build.to_dict() if build else None,
        "methodology": formula_notes(), "references": REFERENCE_LINKS,
        "disclaimer": "Requisitos e desempenho são estimativas. Valide a documentação do modelo, do runtime e do fabricante antes de comprar hardware.",
    }


def export_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_txt(path: Path, payload: dict[str, Any]) -> Path:
    hw = payload["hardware"]
    lines = [
        "BERCHA LIVRENEXO — RELATÓRIO", "=" * 72,
        f"Coletado em: {hw['collected_at']}",
        f"Sistema: {hw['system']['os']} {hw['system']['os_version']}",
        f"CPU: {hw['cpu']['name']} — {hw['cpu']['physical_cores']}C/{hw['cpu']['logical_cores']}T",
        f"RAM: {hw['system']['total_ram_gb']:.1f} GB",
        "GPUs: " + ", ".join(f"{g['name']} ({g['vram_gb']:.1f} GB)" for g in hw["gpus"]),
        "", "RECOMENDAÇÕES (modelo mais avançado primeiro)", "-" * 72,
    ]
    for i, result in enumerate(payload["recommendations"], 1):
        model = result["model"]
        lines.extend([
            f"{i}. {model['display_name']} — {result['status']} ({result['mode']})",
            f"   BerchaScore {model['quality_score']:.1f} | compatibilidade {result['score']:.1f}/100 | {result['estimated_tokens_per_second']}",
            *(f"   + {reason}" for reason in result["reasons"]),
            *(f"   ! {warning}" for warning in result["bottlenecks"]),
        ])
    build = payload.get("build")
    if build:
        lines.extend(["", f"PC PARA {build['target_model']['display_name']}", "-" * 72])
        for component in build["components"]:
            lines.append(f"{component['category']}: {component['product']} — {component['specification']}")
            for store, url in component["search_links"].items():
                lines.append(f"  {store}: {url}")
        lines.append(f"Total indicativo: R$ {build['total_price_brl'][0]:,.0f}–{build['total_price_brl'][1]:,.0f}")
    lines.extend(["", "METODOLOGIA", *[f"- {x}" for x in payload["methodology"]], "", payload["disclaimer"]])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_html(path: Path, payload: dict[str, Any]) -> Path:
    hw = payload["hardware"]
    def esc(value: Any) -> str:
        return html.escape(str(value))
    rows = []
    for result in payload["recommendations"]:
        m = result["model"]
        rows.append(f"<tr><td>{esc(m['display_name'])}</td><td>{esc(m['family'])}</td><td>{m['quality_score']:.1f}</td><td><span class='status'>{esc(result['status'])}</span></td><td>{esc(result['mode'])}</td><td>{esc(result['estimated_tokens_per_second'])}</td><td>{m['recommended_ram_gb']:.1f}</td><td>{m['recommended_vram_gb']:.1f}</td></tr>")
    build_html = ""
    if payload.get("build"):
        build = payload["build"]
        cards = []
        for c in build["components"]:
            links = " · ".join(f"<a href='{html.escape(url, quote=True)}'>{esc(store)}</a>" for store, url in c["search_links"].items())
            cards.append(f"<article><small>{esc(c['category'])}</small><h3>{esc(c['product'])}</h3><p>{esc(c['specification'])}</p><p>{esc(c['reason'])}</p><p>{links}</p></article>")
        build_html = f"<section><h2>Configuração para {esc(build['target_model']['display_name'])}</h2><div class='cards'>{''.join(cards)}</div><p class='price'>Total indicativo: R$ {build['total_price_brl'][0]:,.0f}–{build['total_price_brl'][1]:,.0f}</p></section>"
    refs = "".join(f"<li><a href='{html.escape(url, quote=True)}'>{esc(name)}</a></li>" for name, url in payload["references"].items())
    document = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Relatório Bercha LivreNexo</title><style>
:root{{--bg:#09111f;--card:#111c30;--line:#263753;--text:#eef5ff;--muted:#9cb0ca;--accent:#28d7a1}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:36px}}header{{border-bottom:1px solid var(--line);margin-bottom:28px}}h1{{font-size:34px;margin:0}}h1 b,.status{{color:var(--accent)}}.summary,.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}article{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}}small{{color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}table{{width:100%;border-collapse:collapse;background:var(--card)}}th,td{{padding:10px;border:1px solid var(--line);text-align:left}}th{{color:var(--muted)}}.scroll{{overflow:auto}}a{{color:#7dcfff}}section{{margin:32px 0}}.price{{font-size:20px;color:var(--accent)}}footer{{color:var(--muted);border-top:1px solid var(--line);padding-top:20px}}@media print{{:root{{--bg:white;--card:white;--text:#111;--muted:#444;--line:#bbb}}main{{padding:0}}a{{color:#111}}}}
</style></head><body><main><header><h1>BERCHA <b>LIVRENEXO</b></h1><p>Análise transparente de hardware para IA · {esc(hw['collected_at'])}</p></header>
<section class='summary'><article><small>Processador</small><h3>{esc(hw['cpu']['name'])}</h3><p>{hw['cpu']['physical_cores']} núcleos / {hw['cpu']['logical_cores']} threads</p></article><article><small>Memória</small><h3>{hw['system']['total_ram_gb']:.1f} GB RAM</h3><p>{hw['system']['available_ram_gb']:.1f} GB disponíveis na coleta</p></article><article><small>GPU principal</small><h3>{esc(hw['gpus'][0]['name'] if hw['gpus'] else 'Não detectada')}</h3><p>{max((g['vram_gb'] for g in hw['gpus']), default=0):.1f} GB VRAM</p></article></section>
<section><h2>BerchaMarks — mais avançado primeiro</h2><div class='scroll'><table><thead><tr><th>Modelo</th><th>Família</th><th>Score</th><th>Parecer</th><th>Modo</th><th>Velocidade</th><th>RAM rec.</th><th>VRAM rec.</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
{build_html}<section><h2>Método e fontes</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in payload['methodology'])}</ul><ul>{refs}</ul></section><footer>{esc(payload['disclaimer'])}</footer></main></body></html>"""
    path.write_text(document, encoding="utf-8")
    return path


def export_pdf(path: Path, payload: dict[str, Any]) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("PDF requer o extra opcional: pip install 'bercha-livrenexo[pdf]'") from exc
    def pdf_safe(value: Any) -> str:
        return html.escape(str(value).replace("–", "-").replace("—", "-").replace("‑", "-").replace("−", "-").replace("≈", "~"))

    styles = getSampleStyleSheet()
    compact = ParagraphStyle("Compact", parent=styles["BodyText"], fontSize=8.5, leading=10.5, spaceAfter=0)
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title="Relatório Bercha LivreNexo")
    hw = payload["hardware"]
    story = [Paragraph("Bercha LivreNexo - Relatório", styles["Title"]), Spacer(1, 8),
             Paragraph(f"CPU: {pdf_safe(hw['cpu']['name'])} | RAM: {hw['system']['total_ram_gb']:.1f} GB | "
                       f"VRAM: {max((g['vram_gb'] for g in hw['gpus']), default=0):.1f} GB", styles["BodyText"]), Spacer(1, 12)]
    data = [["Modelo", "BerchaScore", "Parecer", "Modo", "RAM", "VRAM", "Velocidade"]]
    for result in payload["recommendations"][:40]:
        m = result["model"]
        data.append([pdf_safe(m["display_name"][:38]), f"{m['quality_score']:.1f}", pdf_safe(result["status"]), pdf_safe(result["mode"]),
                     f"{m['recommended_ram_gb']:.1f} GB", f"{m['recommended_vram_gb']:.1f} GB", pdf_safe(result["estimated_tokens_per_second"])])
    table = Table(data, repeatRows=1, colWidths=[62 * mm, 22 * mm, 30 * mm, 27 * mm, 18 * mm, 18 * mm, 55 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14243b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), .25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4f8")])]))
    story.append(table)
    if payload.get("build"):
        story.extend([PageBreak(), Paragraph("Configuração recomendada", styles["Heading1"])])
        for component in payload["build"]["components"]:
            story.append(Paragraph(f"<b>{pdf_safe(component['category'])}:</b> {pdf_safe(component['product'])} - {pdf_safe(component['specification'])}", compact))
            story.append(Spacer(1, 2))
    story.extend([Spacer(1, 6), Paragraph("Metodologia e limites", styles["Heading2"])])
    for note in payload["methodology"]:
        story.extend([Paragraph("- " + pdf_safe(note), compact), Spacer(1, 1)])
    story.extend([Spacer(1, 4), Paragraph("Fontes", styles["Heading2"])])
    for name, url in payload["references"].items():
        safe_url = html.escape(str(url), quote=True)
        story.extend([Paragraph(f"- <link href='{safe_url}' color='#145ea8'>{pdf_safe(name)}</link>", compact), Spacer(1, 1)])
    story.extend([Spacer(1, 5), Paragraph(pdf_safe(payload["disclaimer"]), compact)])

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#66758a"))
        canvas.drawString(14 * mm, 7 * mm, "Bercha LivreNexo - análise local e transparente")
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 7 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def export_report(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return export_json(path, payload)
    if suffix == ".txt":
        return export_txt(path, payload)
    if suffix in {".html", ".htm"}:
        return export_html(path, payload)
    if suffix == ".pdf":
        return export_pdf(path, payload)
    raise ValueError("Formato não suportado. Use .html, .txt, .json ou .pdf.")
