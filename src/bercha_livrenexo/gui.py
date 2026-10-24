from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from . import __version__
from .builder import PCBuilder, REFERENCE_LINKS
from .catalog import CatalogDB, OnlineCatalogSync, describe_sync_error
from .hardware import HardwareScanner, quick_benchmark
from .models import AIModel, BuildRecommendation, CompatibilityResult, HardwareReport
from .recommender import CompatibilityEngine, formula_notes
from .reports import export_report, report_payload


BG = "#08111f"
PANEL = "#101c2e"
PANEL_2 = "#15243a"
TEXT = "#edf5ff"
MUTED = "#9db1cb"
ACCENT = "#25d5a0"
BLUE = "#6cb9ff"
WARNING = "#ffbc66"
ERROR = "#ff7185"
BORDER = "#253956"


def _set_text(widget: tk.Text, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


class ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas, style="Body.TFrame")
        self.window = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self.body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(self.window, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class BerchaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Bercha LivreNexo {__version__}")
        self.geometry("1320x820")
        self.minsize(1000, 680)
        self.configure(bg=BG)
        self.option_add("*tearOff", False)
        self.tk.call("tk", "scaling", 1.12)
        self._configure_style()
        self.db = CatalogDB()
        self.hardware: HardwareReport | None = None
        self.results: list[CompatibilityResult] = []
        self.current_build: BuildRecommendation | None = None
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.busy = False
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build_shell()
        self._build_tabs()
        self.after(120, self._poll_events)
        self.after(250, self.scan_hardware)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, bordercolor=BORDER,
                        font=("Segoe UI", 10), focuscolor=ACCENT)
        style.configure("TFrame", background=BG)
        style.configure("Body.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL, relief="flat")
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Metric.TLabel", background=PANEL, foreground=ACCENT, font=("Segoe UI Semibold", 19))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("H2.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 13))
        style.configure("Accent.TButton", background=ACCENT, foreground="#05150f", borderwidth=0, padding=(15, 9), font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", "#52e8ba"), ("disabled", "#395e57")])
        style.configure("TButton", background=PANEL_2, foreground=TEXT, borderwidth=1, padding=(12, 8))
        style.map("TButton", background=[("active", "#203552")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(12, 9), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", PANEL_2)], foreground=[("selected", ACCENT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=29, bordercolor=BORDER)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", padding=(6, 7))
        style.map("Treeview", background=[("selected", "#1d4d54")], foreground=[("selected", TEXT)])
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6, arrowcolor=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=PANEL)

    def _build_shell(self) -> None:
        header = ttk.Frame(self, padding=(22, 14))
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left")
        ttk.Label(brand, text="BERCHA", style="Title.TLabel").pack(side="left")
        tk.Label(brand, text=" LIVRENEXO", bg=BG, fg=ACCENT, font=("Segoe UI Semibold", 20)).pack(side="left")
        ttk.Label(header, text="Inventário e recomendação transparente para IA", style="Muted.TLabel").pack(side="left", padx=20)
        self.scan_button = ttk.Button(header, text="Analisar este PC", style="Accent.TButton", command=self.scan_hardware)
        self.scan_button.pack(side="right")
        self.status_var = tk.StringVar(value="Preparando análise…")
        self.status = ttk.Label(self, textvariable=self.status_var, style="Muted.TLabel", padding=(22, 4))
        self.status.pack(fill="x")
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x")

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(10, 18))
        self.pages: dict[str, ttk.Frame] = {}
        for key, label in [
            ("overview", "Visão geral"), ("cpu", "CPU"), ("caches", "Caches"), ("mainboard", "Placa-mãe"),
            ("memory", "Memória"), ("spd", "SPD"), ("graphics", "Gráficos"), ("storage", "Discos"),
            ("models", "Modelos de IA"), ("builder", "Montar PC"), ("ecosystem", "Fontes online"),
            ("bench", "Bench"), ("reports", "Relatórios"), ("about", "Sobre"),
        ]:
            page = ttk.Frame(self.tabs, padding=18)
            self.tabs.add(page, text=label)
            self.pages[key] = page
        self._build_overview()
        self._build_hardware_pages()
        self._build_models()
        self._build_builder()
        self._build_ecosystem()
        self._build_bench()
        self._build_reports()
        self._build_about()
        self.refresh_ecosystem()

    def _metric(self, parent: tk.Widget, label: str) -> tuple[ttk.Frame, tk.StringVar]:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        ttk.Label(frame, text=label.upper(), style="Panel.TLabel", foreground=MUTED).pack(anchor="w")
        value = tk.StringVar(value="—")
        ttk.Label(frame, textvariable=value, style="Metric.TLabel", wraplength=250).pack(anchor="w", pady=(7, 0))
        return frame, value

    def _build_overview(self) -> None:
        page = self.pages["overview"]
        ttk.Label(page, text="Seu PC para inteligência artificial", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="A análise fica neste computador. Nada é enviado sem você usar Atualizar catálogo.", style="Muted.TLabel").pack(anchor="w", pady=(2, 18))
        metrics = ttk.Frame(page)
        metrics.pack(fill="x")
        self.overview_vars = []
        for column, label in enumerate(("Processador", "Memória RAM", "GPU principal", "Melhor modelo local")):
            frame, var = self._metric(metrics, label)
            frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0), pady=2)
            metrics.columnconfigure(column, weight=1)
            self.overview_vars.append(var)
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=22)
        ttk.Button(actions, text="Atualizar modelos (rápido)", command=lambda: self.sync_catalog(False)).pack(side="left")
        ttk.Button(actions, text="Ver recomendações", command=lambda: self.tabs.select(self.pages["models"])).pack(side="left", padx=8)
        ttk.Button(actions, text="Gerar relatório HTML", command=lambda: self.export_dialog(".html")).pack(side="left")
        ttk.Label(page, text="O que esta análise considera", style="H2.TLabel").pack(anchor="w", pady=(8, 8))
        self.overview_text = tk.Text(page, height=14, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", padx=16, pady=14,
                                     font=("Segoe UI", 10), wrap="word", state="disabled")
        self.overview_text.pack(fill="both", expand=True)

    def _key_value_page(self, page: ttk.Frame) -> ttk.Treeview:
        tree = ttk.Treeview(page, columns=("value",), show="tree headings")
        tree.heading("#0", text="Propriedade")
        tree.heading("value", text="Valor")
        tree.column("#0", width=300)
        tree.column("value", width=700)
        tree.pack(fill="both", expand=True)
        return tree

    def _build_hardware_pages(self) -> None:
        self.cpu_tree = self._key_value_page(self.pages["cpu"])
        self.cache_tree = self._key_value_page(self.pages["caches"])
        self.board_tree = self._key_value_page(self.pages["mainboard"])
        self.memory_tree = self._key_value_page(self.pages["memory"])
        self.spd_tree = ttk.Treeview(self.pages["spd"], columns=("capacity", "type", "speed", "maker", "part"), show="headings")
        for key, label, width in [("capacity", "Capacidade", 120), ("type", "Tipo", 100), ("speed", "Velocidade", 130), ("maker", "Fabricante", 180), ("part", "Part number", 260)]:
            self.spd_tree.heading(key, text=label); self.spd_tree.column(key, width=width)
        self.spd_tree.pack(fill="both", expand=True)
        self.gpu_tree = ttk.Treeview(self.pages["graphics"], columns=("vendor", "vram", "driver", "backend", "compute"), show="tree headings")
        self.gpu_tree.heading("#0", text="GPU")
        for key, label, width in [("vendor", "Fabricante", 120), ("vram", "VRAM", 100), ("driver", "Driver", 160), ("backend", "Backend", 150), ("compute", "Compute", 100)]:
            self.gpu_tree.heading(key, text=label); self.gpu_tree.column(key, width=width)
        self.gpu_tree.pack(fill="both", expand=True)
        self.storage_tree = ttk.Treeview(self.pages["storage"], columns=("kind", "size", "free", "interface"), show="tree headings")
        self.storage_tree.heading("#0", text="Unidade")
        for key, label, width in [("kind", "Tipo", 150), ("size", "Capacidade", 130), ("free", "Livre", 130), ("interface", "Interface", 130)]:
            self.storage_tree.heading(key, text=label); self.storage_tree.column(key, width=width)
        self.storage_tree.pack(fill="both", expand=True)

    def _build_models(self) -> None:
        page = self.pages["models"]
        tools = ttk.Frame(page)
        tools.pack(fill="x", pady=(0, 10))
        ttk.Label(tools, text="Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(tools, textvariable=self.search_var, width=27)
        entry.pack(side="left", padx=7)
        entry.bind("<Return>", lambda _e: self.refresh_models())
        ttk.Button(tools, text="Filtrar", command=self.refresh_models).pack(side="left")
        self.compatible_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(tools, text="Ocultar incompatíveis", variable=self.compatible_only, command=self.refresh_models).pack(side="left", padx=12)
        ttk.Button(tools, text="Atualizar catálogo", command=lambda: self.sync_catalog(False)).pack(side="right")
        ttk.Button(tools, text="Varredura completa", command=lambda: self.sync_catalog(True)).pack(side="right", padx=7)
        pane = ttk.Panedwindow(page, orient="vertical")
        pane.pack(fill="both", expand=True)
        top = ttk.Frame(pane)
        bottom = ttk.Frame(pane)
        pane.add(top, weight=3); pane.add(bottom, weight=1)
        cols = ("rank", "model", "family", "params", "q", "bercha", "status", "mode", "ram", "vram", "source")
        self.model_tree = ttk.Treeview(top, columns=cols, show="headings", selectmode="browse")
        headings = {"rank":"#", "model":"Modelo", "family":"Família", "params":"Parâm.", "q":"Bits", "bercha":"BerchaScore", "status":"Parecer", "mode":"Modo", "ram":"RAM rec.", "vram":"VRAM rec.", "source":"Fonte"}
        widths = {"rank":42, "model":280, "family":100, "params":75, "q":50, "bercha":100, "status":125, "mode":95, "ram":85, "vram":90, "source":100}
        for col in cols:
            self.model_tree.heading(col, text=headings[col]); self.model_tree.column(col, width=widths[col], anchor="w")
        scrollbar = ttk.Scrollbar(top, orient="vertical", command=self.model_tree.yview)
        self.model_tree.configure(yscrollcommand=scrollbar.set)
        self.model_tree.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        self.model_tree.bind("<<TreeviewSelect>>", self._model_selected)
        self.model_tree.bind("<Double-1>", lambda _e: self.open_selected_model())
        detail_actions = ttk.Frame(bottom)
        detail_actions.pack(side="right", fill="y", padx=(10, 0))
        ttk.Button(detail_actions, text="Abrir fonte", command=self.open_selected_model).pack(fill="x", pady=(0, 7))
        ttk.Button(detail_actions, text="Montar PC", style="Accent.TButton", command=self.build_from_selected).pack(fill="x")
        self.model_detail = tk.Text(bottom, height=8, bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=10, wrap="word", state="disabled")
        self.model_detail.pack(side="left", fill="both", expand=True)

    def _build_builder(self) -> None:
        page = self.pages["builder"]
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Label(bar, text="Modelo-alvo:").pack(side="left")
        self.build_model_var = tk.StringVar()
        self.build_combo = ttk.Combobox(bar, textvariable=self.build_model_var, width=50, state="readonly")
        self.build_combo.pack(side="left", padx=8)
        ttk.Button(bar, text="Calcular configuração", style="Accent.TButton", command=self.generate_build).pack(side="left")
        self.build_total_var = tk.StringVar(value="Escolha um modelo local com requisitos conhecidos.")
        ttk.Label(bar, textvariable=self.build_total_var, foreground=ACCENT).pack(side="right")
        self.build_tree = ttk.Treeview(page, columns=("product", "spec", "price", "required"), show="tree headings")
        self.build_tree.heading("#0", text="Componente")
        for key, label, width in [("product", "Recomendação", 310), ("spec", "Especificação", 360), ("price", "Faixa offline", 150), ("required", "Status", 100)]:
            self.build_tree.heading(key, text=label); self.build_tree.column(key, width=width)
        self.build_tree.pack(fill="both", expand=True)
        self.build_tree.bind("<<TreeviewSelect>>", self._build_component_selected)
        bottom = ttk.Frame(page)
        bottom.pack(fill="x", pady=(10, 0))
        self.build_detail = tk.Text(bottom, height=5, bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=10, wrap="word", state="disabled")
        self.build_detail.pack(side="left", fill="both", expand=True)
        self.shop_button = ttk.Button(bottom, text="Abrir lojas", command=self.open_component_shops, state="disabled")
        self.shop_button.pack(side="right", padx=(10, 0))

    def _build_ecosystem(self) -> None:
        page = self.pages["ecosystem"]
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Projetos, runtimes e repositórios encontrados no GitHub. Eles não entram no ranking sem requisitos verificáveis.", style="Muted.TLabel").pack(side="left")
        ttk.Button(bar, text="Atualizar fontes", command=lambda: self.sync_catalog(False)).pack(side="right")
        self.eco_tree = ttk.Treeview(page, columns=("description", "stars", "license", "updated"), show="tree headings")
        self.eco_tree.heading("#0", text="Projeto")
        for key, label, width in [("description", "Descrição", 480), ("stars", "Stars", 80), ("license", "Licença", 110), ("updated", "Atualizado", 170)]:
            self.eco_tree.heading(key, text=label); self.eco_tree.column(key, width=width)
        self.eco_tree.pack(fill="both", expand=True)
        self.eco_tree.bind("<Double-1>", lambda _e: self.open_ecosystem())

    def _build_bench(self) -> None:
        page = self.pages["bench"]
        ttk.Label(page, text="Microbenchmark Bercha LivreNexo", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Mede um pequeno kernel numérico em uma thread. Serve para comparar versões deste mesmo PC; não substitui tokens/s reais.", style="Muted.TLabel").pack(anchor="w", pady=(3, 18))
        ttk.Button(page, text="Iniciar benchmark", style="Accent.TButton", command=self.run_benchmark).pack(anchor="w")
        self.bench_text = tk.Text(page, height=18, bg=PANEL, fg=TEXT, relief="flat", padx=18, pady=16, font=("Consolas", 11), state="disabled")
        self.bench_text.pack(fill="both", expand=True, pady=(16, 0))

    def _build_reports(self) -> None:
        page = self.pages["reports"]
        ttk.Label(page, text="Relatório compartilhável", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Seriais são ocultados por padrão para proteger sua privacidade.", style="Muted.TLabel").pack(anchor="w", pady=(3, 18))
        form = ttk.Frame(page, style="Panel.TFrame", padding=22)
        form.pack(fill="x")
        ttk.Label(form, text="Formato", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=7)
        self.report_format = tk.StringVar(value="HTML (recomendado)")
        ttk.Combobox(form, textvariable=self.report_format, values=("HTML (recomendado)", "PDF", "TXT", "JSON"), state="readonly", width=25).grid(row=0, column=1, sticky="w", padx=12)
        self.include_serials = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Incluir números de série", variable=self.include_serials, style="TCheckbutton").grid(row=1, column=1, sticky="w", padx=12, pady=7)
        ttk.Button(form, text="Escolher local e gerar", style="Accent.TButton", command=self.export_dialog).grid(row=2, column=1, sticky="w", padx=12, pady=12)
        self.report_status = tk.StringVar(value="O relatório incluirá hardware, recomendações, método, fontes e a configuração de PC atual (se houver).")
        ttk.Label(page, textvariable=self.report_status, wraplength=900, style="Muted.TLabel").pack(anchor="w", pady=16)

    def _build_about(self) -> None:
        page = self.pages["about"]
        about = tk.Text(page, bg=BG, fg=TEXT, relief="flat", padx=10, pady=10, font=("Segoe UI", 11), wrap="word")
        about.pack(fill="both", expand=True)
        content = [
            f"Bercha LivreNexo {__version__}\n\n",
            "Software livre, gratuito e multiplataforma para compreender o hardware necessário à IA local.\n\n",
            "Privacidade\nA varredura de hardware é local. Somente a opção Atualizar catálogo consulta Hugging Face e GitHub. Tokens ficam apenas no ambiente do processo e não aparecem em relatórios.\n\n",
            "Como ler os resultados\n" + "\n".join(f"• {line}" for line in formula_notes()) + "\n\n",
            "Limites honestos\nFonte, gabinete, cooler e compatibilidade física raramente são expostos pelo sistema operacional. O montador propõe uma configuração-alvo, mas uma pessoa qualificada deve conferir peças e instalação elétrica.\n\n",
            "Licença\nGNU General Public License v3 ou posterior. Este programa é fornecido sem qualquer garantia. Sem telemetria, publicidade ou links afiliados.\n\n",
            "Fontes metodológicas\n" + "\n".join(f"• {name}: {url}" for name, url in REFERENCE_LINKS.items()),
        ]
        about.insert("1.0", "".join(content)); about.configure(state="disabled")

    def _set_busy(self, value: bool, message: str = "") -> None:
        self.busy = value
        self.scan_button.configure(state="disabled" if value else "normal")
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()
        if message:
            self.status_var.set(message)

    def _background(self, operation: Callable[[], Any], success_event: str) -> None:
        def worker() -> None:
            try:
                self.events.put((success_event, operation()))
            except Exception as exc:
                self.events.put(("error", exc))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == "hardware":
                    self.hardware = data
                    self._render_hardware()
                    self._set_busy(False, f"Análise concluída · catálogo com {self.db.count():,} registros")
                elif event == "sync_progress":
                    self.status_var.set(str(data))
                elif event == "sync_done":
                    self._set_busy(False, f"Catálogo atualizado: {data[0]:,} modelos e {data[1]:,} projetos nesta execução")
                    self._recalculate()
                    self.refresh_ecosystem()
                    if data[2]:
                        messagebox.showwarning("Sincronização parcial", "\n".join(data[2]))
                elif event == "bench":
                    self._set_busy(False, "Benchmark concluído")
                    _set_text(self.bench_text, "PONTUAÇÃO BERCHA CPU\n\n" + f"{data['score']:,} pontos\n\n" + f"Operações/s: {data['operations_per_second']:,}\nTempo: {data['elapsed_seconds']} s\nThreads: {data['threads']}\n\n{data['note']}")
                elif event == "error":
                    self._set_busy(False, "A operação não foi concluída")
                    messagebox.showerror("Bercha LivreNexo", describe_sync_error(data))
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def scan_hardware(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Analisando CPU, placa-mãe, memória, GPU e discos…")
        self._background(HardwareScanner().scan, "hardware")

    def _render_hardware(self) -> None:
        assert self.hardware
        h = self.hardware
        self.overview_vars[0].set(h.cpu.name[:38])
        self.overview_vars[1].set(f"{h.system.total_ram_gb:.1f} GB")
        self.overview_vars[2].set((max(h.gpus, key=lambda g: g.vram_gb).name if h.gpus else "Não detectada")[:38])
        self._fill_pairs(self.cpu_tree, [("Modelo", h.cpu.name), ("Fabricante", h.cpu.vendor), ("Arquitetura", h.cpu.architecture),
            ("Núcleos / threads", f"{h.cpu.physical_cores} / {h.cpu.logical_cores}"), ("Clock máximo", f"{h.cpu.max_clock_mhz} MHz"),
            ("Socket", h.cpu.socket), ("Virtualização no firmware", str(h.cpu.virtualization)), ("Instruções confirmadas", ", ".join(h.cpu.instruction_sets) or "Não confirmadas")])
        self._fill_pairs(self.cache_tree, [("Cache L2", f"{h.cpu.cache_l2_kb:,} KB"), ("Cache L3", f"{h.cpu.cache_l3_kb:,} KB")])
        b = h.mainboard
        self._fill_pairs(self.board_tree, [("Fabricante", b.manufacturer), ("Modelo", b.product), ("Versão", b.version),
            ("Número de série", b.serial), ("Fabricante da BIOS", b.bios_vendor), ("Versão da BIOS", b.bios_version), ("Data da BIOS", b.bios_date)])
        self._fill_pairs(self.memory_tree, [("RAM total", f"{h.system.total_ram_gb:.1f} GB"), ("RAM disponível", f"{h.system.available_ram_gb:.1f} GB"),
            ("Módulos detectados", str(len(h.memory_modules))), ("Slots usados", ", ".join(x.slot for x in h.memory_modules) or "Não informado")])
        self._clear(self.spd_tree)
        for m in h.memory_modules:
            self.spd_tree.insert("", "end", text=m.slot, values=(f"{m.capacity_gb:.1f} GB", m.memory_type, f"{m.configured_speed_mhz or m.speed_mhz} MT/s", m.manufacturer, m.part_number))
        self._clear(self.gpu_tree)
        for g in h.gpus:
            self.gpu_tree.insert("", "end", text=g.name, values=(g.vendor, f"{g.vram_gb:.1f} GB", g.driver, g.backend, g.compute_capability))
        self._clear(self.storage_tree)
        for d in h.storage:
            self.storage_tree.insert("", "end", text=d.name, values=(d.kind, f"{d.size_gb:.1f} GB", f"{d.free_gb:.1f} GB", d.interface))
        warnings = "\n".join(f"Atenção: {x}" for x in h.warnings) or "Nenhum alerta crítico na coleta."
        _set_text(self.overview_text, f"Sistema: {h.system.os} {h.system.os_version}\nPlaca-mãe: {b.manufacturer} {b.product}\nGPU/VRAM: " + ", ".join(f"{g.name} ({g.vram_gb:.1f} GB)" for g in h.gpus) + f"\nEspaço livre analisado: {h.total_storage_free_gb:.1f} GB\n\n{warnings}\n\nA recomendação usa parâmetros, quantização, RAM, VRAM, disco, runtime e licença. Fonte, cooler e gabinete não podem ser identificados com confiança por software comum.")
        self._recalculate()

    def _recalculate(self) -> None:
        if not self.hardware:
            return
        models = self.db.list_models(local_only=True, known_requirements_only=True, limit=5000)
        self.results = CompatibilityEngine().rank(self.hardware, models, include_incompatible=True)
        compatible = next((r for r in self.results if r.status not in {"Incompatível", "Dados insuficientes"}), None)
        self.overview_vars[3].set(compatible.model.display_name[:38] if compatible else "Nenhum confirmado")
        choices = [f"{r.model.display_name}  ·  {r.model.model_id}" for r in self.results]
        self.build_combo.configure(values=choices)
        if choices and not self.build_model_var.get():
            self.build_model_var.set(choices[0])
        self.refresh_models()

    def refresh_models(self) -> None:
        self._clear(self.model_tree)
        shown = 0
        query = self.search_var.get().lower().strip() if hasattr(self, "search_var") else ""
        for result in self.results:
            m = result.model
            if query and query not in f"{m.display_name} {m.model_id} {m.family}".lower():
                continue
            if self.compatible_only.get() and result.status in {"Incompatível", "Dados insuficientes"}:
                continue
            shown += 1
            self.model_tree.insert("", "end", iid=str(shown - 1), values=(shown, m.display_name, m.family, f"{m.parameters_b:g}B", m.quantization_bits,
                f"{m.quality_score:.1f}", result.status, result.mode, f"{m.recommended_ram_gb:.0f} GB", f"{m.recommended_vram_gb:.0f} GB", m.source), tags=(result.status,))
            if shown >= 1000:
                break
        for tag, color in [("Excelente", ACCENT), ("Compatível", BLUE), ("Compatível, lento", WARNING), ("Limítrofe", WARNING), ("Incompatível", ERROR)]:
            self.model_tree.tag_configure(tag, foreground=color)

    def _selected_result(self) -> CompatibilityResult | None:
        selection = self.model_tree.selection()
        if not selection:
            return None
        values = self.model_tree.item(selection[0], "values")
        if not values:
            return None
        display_name = values[1]
        return next((r for r in self.results if r.model.display_name == display_name), None)

    def _model_selected(self, _event: tk.Event | None = None) -> None:
        result = self._selected_result()
        if not result:
            return
        m = result.model
        details = [f"{m.display_name} · {m.model_id}", f"Parecer: {result.status} | modo: {result.mode} | compatibilidade: {result.score:.1f}/100",
                   f"{result.estimated_tokens_per_second} | licença: {m.license} | confiança: {m.confidence}", ""]
        details.extend(f"✓ {x}" for x in result.reasons)
        details.extend(f"! {x}" for x in result.bottlenecks)
        _set_text(self.model_detail, "\n".join(details))

    def open_selected_model(self) -> None:
        result = self._selected_result()
        if result and result.model.source_url:
            webbrowser.open(result.model.source_url)

    def build_from_selected(self) -> None:
        result = self._selected_result()
        if not result:
            return
        choice = next((x for x in self.build_combo["values"] if x.endswith(result.model.model_id)), "")
        self.build_model_var.set(choice)
        self.generate_build()
        self.tabs.select(self.pages["builder"])

    def generate_build(self) -> None:
        if not self.hardware:
            messagebox.showinfo("Bercha LivreNexo", "Aguarde a análise do hardware.")
            return
        selection = self.build_model_var.get()
        model_id = selection.split("  ·  ", 1)[-1] if "  ·  " in selection else ""
        model = self.db.get_model(model_id)
        if not model:
            messagebox.showwarning("Bercha LivreNexo", "Escolha um modelo válido.")
            return
        self.current_build = PCBuilder().build(model, self.hardware)
        self._clear(self.build_tree)
        for index, c in enumerate(self.current_build.components):
            price = f"R$ {c.estimated_price_brl[0]:,.0f}–{c.estimated_price_brl[1]:,.0f}"
            self.build_tree.insert("", "end", iid=str(index), text=c.category, values=(c.product, c.specification, price, "Essencial" if c.required else "Opcional"))
        lo, hi = self.current_build.total_price_brl
        self.build_total_var.set(f"Total indicativo: R$ {lo:,.0f}–{hi:,.0f}")
        _set_text(self.build_detail, "\n".join(self.current_build.caveats))

    def _build_component_selected(self, _event: tk.Event | None = None) -> None:
        if not self.current_build or not self.build_tree.selection():
            return
        c = self.current_build.components[int(self.build_tree.selection()[0])]
        _set_text(self.build_detail, f"{c.reason}\n\nLinks de busca sem afiliação: " + ", ".join(c.search_links))
        self.shop_button.configure(state="normal")

    def open_component_shops(self) -> None:
        if not self.current_build or not self.build_tree.selection():
            return
        component = self.current_build.components[int(self.build_tree.selection()[0])]
        if not messagebox.askyesno("Abrir lojas", "Abrir quatro pesquisas no navegador? Preços e vendedores não são validados pelo Bercha LivreNexo."):
            return
        for url in component.search_links.values():
            webbrowser.open_new_tab(url)

    def sync_catalog(self, full: bool) -> None:
        if self.busy:
            return
        if full and not messagebox.askyesno("Varredura completa", "O Hugging Face contém muitos modelos. A indexação completa pode demorar bastante e usar centenas de MB. Continuar?"):
            return
        self._set_busy(True, "Iniciando sincronização pública…")
        def operation() -> tuple[int, int, list[str]]:
            syncer = OnlineCatalogSync(self.db)
            progress = lambda _count, msg: self.events.put(("sync_progress", msg))
            hf = gh = 0
            warnings: list[str] = []
            try:
                hf = syncer.sync_huggingface(limit=None if full else 500, token=os.environ.get("HF_TOKEN", ""), progress=progress)
            except Exception as exc:
                warnings.append("Hugging Face: " + describe_sync_error(exc))
            try:
                gh = syncer.sync_github(token=os.environ.get("GITHUB_TOKEN", ""), progress=progress)
            except Exception as exc:
                warnings.append("GitHub: " + describe_sync_error(exc))
            if not hf and not gh:
                raise RuntimeError("Nenhuma fonte pôde ser atualizada. " + " ".join(warnings))
            return hf, gh, warnings
        self._background(operation, "sync_done")

    def refresh_ecosystem(self) -> None:
        self._clear(self.eco_tree)
        for index, item in enumerate(self.db.list_ecosystem(200)):
            self.eco_tree.insert("", "end", iid=f"eco-{index}", text=item["name"], values=(item["description"], item["stars"], item["license"], item["updated_at"]), tags=(item["url"],))

    def open_ecosystem(self) -> None:
        if not self.eco_tree.selection():
            return
        tags = self.eco_tree.item(self.eco_tree.selection()[0], "tags")
        if tags:
            webbrowser.open(tags[0])

    def run_benchmark(self) -> None:
        if self.busy:
            return
        self._set_busy(True, "Executando benchmark curto…")
        self._background(quick_benchmark, "bench")

    def export_dialog(self, forced_extension: str = "") -> None:
        if not self.hardware:
            messagebox.showinfo("Bercha LivreNexo", "Aguarde a análise do hardware.")
            return
        mapping = {"HTML (recomendado)": ".html", "PDF": ".pdf", "TXT": ".txt", "JSON": ".json"}
        extension = forced_extension or mapping.get(self.report_format.get(), ".html")
        types = {".html": [("Página HTML", "*.html")], ".pdf": [("Documento PDF", "*.pdf")], ".txt": [("Texto", "*.txt")], ".json": [("Dados JSON", "*.json")]}
        filename = filedialog.asksaveasfilename(title="Salvar relatório", defaultextension=extension, filetypes=types[extension], initialfile="relatorio-bercha-livrenexo" + extension)
        if not filename:
            return
        try:
            payload = report_payload(self.hardware, self.results[:50], self.current_build, self.include_serials.get())
            path = export_report(Path(filename), payload)
            self.report_status.set(f"Relatório salvo em {path}")
            if messagebox.askyesno("Relatório concluído", "Arquivo criado com sucesso. Deseja abri-lo agora?"):
                os.startfile(path) if os.name == "nt" else webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror("Falha ao exportar", str(exc))

    @staticmethod
    def _clear(tree: ttk.Treeview) -> None:
        tree.delete(*tree.get_children())

    @staticmethod
    def _fill_pairs(tree: ttk.Treeview, rows: list[tuple[str, Any]]) -> None:
        tree.delete(*tree.get_children())
        for key, value in rows:
            tree.insert("", "end", text=key, values=(value,))

    def _close(self) -> None:
        try:
            self.db.close()
        finally:
            self.destroy()


def main() -> None:
    try:
        app = BerchaApp()
        app.mainloop()
    except tk.TclError as exc:
        raise RuntimeError(f"Tk não está disponível neste sistema: {exc}") from exc


if __name__ == "__main__":
    main()
