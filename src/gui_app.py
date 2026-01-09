"""AudioCinema GUI mockup."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "audiocinema.png"

BACKGROUND = "#f4f5f7"
SIDEBAR_BG = "#eef0f3"
ACCENT = "#8b939c"
TEXT_PRIMARY = "#2d2f33"


def build_plot(parent: tk.Widget) -> FigureCanvasTkAgg:
    figure = Figure(figsize=(3.2, 2.4), dpi=100, facecolor="white")
    axis = figure.add_subplot(111)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axis.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axis.grid(False)
    axis.set_facecolor("white")
    canvas = FigureCanvasTkAgg(figure, master=parent)
    canvas.draw()
    return canvas


def create_app() -> tk.Tk:
    root = tk.Tk()
    root.title("AudioCinema")
    root.geometry("980x720")
    root.configure(background=BACKGROUND)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
    style.configure(
        "Sidebar.TLabel",
        background=SIDEBAR_BG,
        foreground=TEXT_PRIMARY,
    )
    style.configure(
        "Title.TLabel",
        background=SIDEBAR_BG,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 16, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=SIDEBAR_BG,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Action.TButton",
        background=ACCENT,
        foreground="white",
        font=("Segoe UI", 10, "bold"),
        padding=(12, 8),
        borderwidth=0,
    )
    style.map(
        "Action.TButton",
        background=[("active", "#7b848e")],
    )
    style.configure(
        "Status.TLabel",
        background=BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 10, "bold"),
    )

    root.columnconfigure(0, weight=0)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    sidebar = ttk.Frame(root, padding=16, style="Sidebar.TFrame")
    sidebar.grid(row=0, column=0, sticky="ns")

    separator = ttk.Separator(root, orient="vertical")
    separator.grid(row=0, column=1, sticky="nsw")

    content = ttk.Frame(root, padding=16)
    content.grid(row=0, column=1, sticky="nsew")
    content.columnconfigure(0, weight=1)
    content.rowconfigure(1, weight=1)

    if LOGO_PATH.exists():
        logo_image = tk.PhotoImage(file=str(LOGO_PATH))
        logo_label = ttk.Label(sidebar, image=logo_image, style="Sidebar.TLabel")
        logo_label.image = logo_image
        logo_label.pack(pady=(0, 8))

    ttk.Label(
        sidebar,
        text="AudioCinema",
        style="Title.TLabel",
    ).pack()

    ttk.Label(
        sidebar,
        text=(
            "Record, evaluate and analyze your\n"
            "audio system to ensure the best\n"
            "immersive experience."
        ),
        justify="center",
        style="Subtitle.TLabel",
    ).pack(pady=(6, 18))

    ttk.Button(sidebar, text="Settings", style="Action.TButton").pack(
        fill="x", pady=4
    )
    ttk.Button(sidebar, text="Record Reference", style="Action.TButton").pack(
        fill="x", pady=4
    )
    ttk.Button(sidebar, text="Record Test", style="Action.TButton").pack(
        fill="x", pady=4
    )

    ttk.Label(sidebar, text="Messages:", style="Sidebar.TLabel").pack(
        anchor="w", pady=(16, 6)
    )
    message_box = tk.Text(
        sidebar,
        width=26,
        height=10,
        wrap="word",
        relief="solid",
        borderwidth=1,
        background="white",
        font=("Segoe UI", 9),
    )
    message_box.insert(
        "1.0",
        "• Set everything up in Settings,\n"
        "  record the reference, and\n"
        "  start evaluating by recording\n"
        "  the test.",
    )
    message_box.configure(state="disabled")
    message_box.pack()

    info_frame = ttk.Frame(content)
    info_frame.grid(row=0, column=0, sticky="ew")
    info_frame.columnconfigure(1, weight=1)

    ttk.Label(info_frame, text="TEST:").grid(row=0, column=0, sticky="w", padx=(0, 8))
    test_entry = ttk.Entry(info_frame)
    test_entry.insert(0, "Test_2026-01-09_07-23-53")
    test_entry.grid(row=0, column=1, sticky="ew")

    ttk.Label(info_frame, text="EVALUATION:").grid(
        row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0)
    )
    ttk.Label(info_frame, text="FAILED", style="Status.TLabel").grid(
        row=1, column=1, sticky="w", pady=(8, 0)
    )

    plots_frame = ttk.Frame(content)
    plots_frame.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
    for row in range(2):
        plots_frame.rowconfigure(row, weight=1)
    for column in range(2):
        plots_frame.columnconfigure(column, weight=1)

    for index in range(4):
        row, column = divmod(index, 2)
        plot_container = ttk.Frame(plots_frame, padding=8)
        plot_container.grid(row=row, column=column, padx=12, pady=12, sticky="nsew")
        canvas = build_plot(plot_container)
        canvas.get_tk_widget().pack(fill="both", expand=True)

    return root


if __name__ == "__main__":
    app = create_app()
    app.mainloop()
