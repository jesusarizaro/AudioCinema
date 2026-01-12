
import os, json, traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Any

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

import numpy as np
import sounddevice as sd
import soundfile as sf
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from app_platform import APP_DIR, ASSETS_DIR, ensure_dirs
from configio import load_config, save_config
from analyzer import (
    normalize_mono, record_audio, analyze_pair,
    detect_beeps, build_segments, build_json_payload
)
from iot_tb import send_json_to_thingsboard

APP_NAME = "AudioCinema"
SAVE_DIR = (APP_DIR / "data" / "captures").absolute()
EXPORT_DIR = (APP_DIR / "data" / "reports").absolute()
SAVE_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

ENV_INPUT_INDEX = os.environ.get("AUDIOCINEMA_INPUT_INDEX")




REF_CUTOFF_LOW_HZ = 30.0
REF_CUTOFF_HIGH_HZ = 8000.0


#----------------------------------------------------------------------------------------------------------------Texto que aparece en el Boton "Information"
INFO_TEXT = (
    "AudioCinema\n\n"
    "This application records, evaluates, and compares a TEST track with a "
    "REFERENCE track to verify the status of the audio system.\n\n"
    "What it does:\n"
    "• Records the test track using the microphone.\n"
    "• Compares against the reference (RMS, crest, bands, relative spectrum, P95).\n"
    "• Displays the waveform of both tracks.\n"
    "• Exports a JSON with results and (optionally) sends it to ThingsBoard.\n\n"
    "Suggestions:\n"
    "• Use the same microphone position for each test.\n"
    "• Verify the reference file in Settings."
)

# ---------- util mic ----------
def pick_input_device(preferred_name_substr: Optional[str] = None) -> Optional[int]:
    import sounddevice as sd
    try:
        devices = sd.query_devices()
    except Exception:
        return None

    if ENV_INPUT_INDEX:
        try:
            idx = int(ENV_INPUT_INDEX)
            if 0 <= idx < len(devices) and devices[idx].get("max_input_channels",0) > 0:
                return idx
        except Exception:
            pass

    if preferred_name_substr:
        s = preferred_name_substr.lower()
        for i, d in enumerate(devices):
            if s in str(d.get("name","")).lower() and d.get("max_input_channels",0) > 0:
                return i

    for i, d in enumerate(devices):
        if d.get("max_input_channels",0) > 0:
            return i
    return None

# ---------- decorador para mostrar errores UI ----------
def ui_action(fn):
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as e:
            tb_str = traceback.format_exc()
            try:
                messagebox.showerror(APP_NAME, f"{e}\n\n{tb_str}")
            except Exception:
                print(tb_str)
            return None
    return wrapper


class AudioCinemaGUI:
    def __init__(self, root: tb.Window):
        self.root = root
        self.root.title(APP_NAME)

        # Tema y fondo gris
        tb.Style(theme="flatly")
        try:
            self.root.configure(bg="#e6e6e6")
        except Exception:
            pass

        # Icono en ventana
        self._icon_img = None
        try:
            icon_path = ASSETS_DIR / "audiocinema.png"
            if icon_path.exists():
                self._icon_img = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            self._icon_img = None
        try:
            self.root.wm_class(APP_NAME, APP_NAME)
        except Exception:
            pass

        ensure_dirs()
        self.cfg = load_config()

        # Variables visibles (cabecera)
        self.fs = tk.IntVar(value=int(self._cfg(["audio","fs"], 48000)))
        self.duration = tk.DoubleVar(value=float(self._cfg(["audio","duration_s"], 10.0)))

        self.input_device_index: Optional[int] = None
        self.test_name = tk.StringVar(value="—")
        self.eval_text = tk.StringVar(value="—")

        # buffers de ondas últimas
        self.last_ref: Optional[np.ndarray] = None
        self.last_cur: Optional[np.ndarray] = None
        self.last_fs: int = int(self.fs.get())

        # markers/segments para JSON
        self.ref_markers: List[int] = []
        self.cur_markers: List[int] = []
        self.ref_segments: List[Tuple[int,int]] = []
        self.cur_segments: List[Tuple[int,int]] = []

        self._build_ui()
        self._auto_select_input_device()

    # --- helpers cfg seguros ---
    def _cfg(self, path: List[str], default: Any = None) -> Any:
        d = self.cfg
        for key in path:
            if not isinstance(d, dict) or key not in d:
                return default
            d = d[key]
        return d

    def _set_cfg(self, path: List[str], value: Any) -> None:
        d = self.cfg
        for key in path[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[path[-1]] = value

    # --------------------- UI ---------------------
    def _build_ui(self):
        root_frame = ttk.Frame(self.root, padding=8)
        root_frame.pack(fill=BOTH, expand=True)

        paned = ttk.Panedwindow(root_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        # --------- IZQUIERDA: logo + 4 botones ---------
        left = ttk.Frame(paned, padding=(6,6))
        paned.add(left, weight=1)

        card = ttk.Frame(left, padding=6)
        card.pack(fill=Y, expand=False)

        if self._icon_img is not None:
            ttk.Label(card, image=self._icon_img).pack(anchor="n", pady=(0,4))
        ttk.Label(card, text="AudioCinema", font=("Segoe UI", 18, "bold")).pack(anchor="n")

        desc = ("Record, evaluate, and analyze your audio system "
                "to ensure the best immersive experience.")
        ttk.Label(card, text=desc, wraplength=220, justify="center").pack(anchor="n", pady=(6,10))

        btn_style = {"bootstyle": PRIMARY, "width": 20}
        tb.Button(card, text="Information",   command=self._show_info, **btn_style).pack(pady=6, fill=X)
        tb.Button(card, text="Settings", command=self._popup_settings, **btn_style).pack(pady=6, fill=X)
        tb.Button(card, text="Record Test",  command=self._run_once, **btn_style).pack(pady=(6,0), fill=X)

        # separador vertical
        sep = ttk.Separator(root_frame, orient=VERTICAL)
        paned.add(sep)

        # --------- DERECHA: cabecera + ondas + mensajes ---------
        right = ttk.Frame(paned, padding=(8,6))
        paned.add(right, weight=4)

        header = ttk.Frame(right)
        header.pack(fill=X, pady=(0,8))

        ttk.Label(header, text="TEST:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0,6))
        e = ttk.Entry(header, textvariable=self.test_name, width=32, state="readonly", justify="center")
        e.grid(row=0, column=1, sticky="w")

        ttk.Label(header, text="SCORE:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=(0,6), pady=(6,0))
        self.eval_lbl = ttk.Label(header, textvariable=self.eval_text, font=("Segoe UI", 11, "bold"), foreground="#333")
        self.eval_lbl.grid(row=1, column=1, sticky="w", pady=(6,0))

        fig_card = ttk.Frame(right, padding=4)
        fig_card.pack(fill=BOTH, expand=True)

        self.fig = Figure(figsize=(5,4), dpi=100)
        self.ax_ref = self.fig.add_subplot(2,1,1)
        self.ax_cur = self.fig.add_subplot(2,1,2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=fig_card)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)
        self._clear_waves()
        self.fig.tight_layout()

        # Mensajes
        msg_card = ttk.Frame(right, padding=4)
        msg_card.pack(fill=BOTH, expand=False, pady=(6,0))
        ttk.Label(msg_card, text="Messages", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.msg_text = tk.Text(msg_card, height=6, wrap="word")
        self.msg_text.pack(fill=BOTH, expand=True)
        self._set_messages(["Ready?. Press «Record Test» to start."])

    def _clear_waves(self):
        for ax, title in ((self.ax_ref, "Reference track"), (self.ax_cur, "Test track")):
            ax.clear()
            ax.set_title(title)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Amplitude")
            ax.grid(True, axis='x', ls=':')
        self.canvas.draw_idle()

    def _plot_wave(self, ax, x: np.ndarray, fs: int):
        n = len(x)
        t = np.arange(n, dtype=np.float32) / float(fs if fs else 1)
        ax.plot(t, x, linewidth=0.8)
        ax.set_xlim(0.0, float(t[-1]) if n else 1.0)

    def _set_eval(self, passed: Optional[bool]):
        if passed is None:
            self.eval_text.set("—")
            self.eval_lbl.configure(foreground="#333333")
        elif passed:
            self.eval_text.set("PASSED")
            self.eval_lbl.configure(foreground="#0d8a00")
        else:
            self.eval_text.set("FAILED")
            self.eval_lbl.configure(foreground="#cc0000")

    def _set_messages(self, lines: List[str]):
        self.msg_text.delete("1.0", tk.END)
        for ln in lines:
            self.msg_text.insert(tk.END, "• " + ln + "\n")
        self.msg_text.see(tk.END)

    # ----------------- acciones -----------------
    def _auto_select_input_device(self):
        pref = str(self._cfg(["audio","preferred_input_name"], ""))
        self.input_device_index = pick_input_device(pref)

    @ui_action
    def _show_info(self):
        messagebox.showinfo(APP_NAME, INFO_TEXT)



    @ui_action
    def _popup_settings(self):
        w = tk.Toplevel(self.root)
        w.title("Settings")
        if self._icon_img is not None:
            try:
                w.iconphoto(True, self._icon_img)
                w.wm_class(APP_NAME, APP_NAME)
            except Exception:
                pass

        frm = ttk.Frame(w, padding=10); frm.pack(fill=BOTH, expand=True)
        nb = ttk.Notebook(frm); nb.pack(fill=BOTH, expand=True)

        #----------------------------------------------------------------------------------------------------------------ventana "Schedule"
        g = ttk.Frame(nb); nb.add(g, text="Schedule")
        oncal_var = tk.StringVar(value=self._cfg(["oncalendar"], "*-*-* 02:00:00"))
        ttk.Label(g, text="OnCalendar (systemd):").grid(row=0, column=0, sticky="w", pady=(6,2))
        ttk.Entry(g, textvariable=oncal_var, width=30).grid(row=0, column=1, sticky="w", pady=(6,2))

        #----------------------------------------------------------------------------------------------------------------ventana "Tracks & Mic"
        a = ttk.Frame(nb); nb.add(a, text="Track's time & Mic")
        fs_var = tk.IntVar(value=int(self._cfg(["audio","fs"], 48000)))
        dur_var = tk.DoubleVar(value=float(self._cfg(["audio","duration_s"], 10.0)))
        pref_in = tk.StringVar(value=self._cfg(["audio","preferred_input_name"], ""))

        ttk.Label(a, text="Duration (s):").grid(row=0, column=0, sticky="w", pady=(6,2))
        ttk.Entry(a, textvariable=dur_var, width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(a, text="Microphone:").grid(row=1, column=0, sticky="w", pady=(6,2))
        device_options = []
        try:
            devices = sd.query_devices()
        except Exception:
            devices = []
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                device_options.append(f"{i}: {d.get('name', 'Unknown')}")
        if not device_options:
            device_options = ["No input devices detected"]
        device_var = tk.StringVar(value=device_options[0])
        for opt in device_options:
            if pref_in.get() and pref_in.get() in opt:
                device_var.set(opt)
                break
        device_combo = ttk.Combobox(a, textvariable=device_var, values=device_options, state="readonly", width=28)
        device_combo.grid(row=1, column=1, sticky="w")

        #----------------------------------------------------------------------------------------------------------------ventana "Record Reference"
        r = ttk.Frame(nb); nb.add(r, text="Record Reference")
        ref_var = tk.StringVar(value=self._cfg(["reference","wav_path"], str(ASSETS_DIR/"reference_master.wav")))

        r.columnconfigure(0, weight=1)
        r.columnconfigure(1, weight=1)

        
        ref_path_var = tk.StringVar(value=f"Reference track will be saved to: {ref_var.get()}")
        cutoff_var = tk.StringVar(value=f"Cutoff range: {REF_CUTOFF_LOW_HZ:.0f} Hz - {REF_CUTOFF_HIGH_HZ:.0f} Hz")
        recorded_var = tk.StringVar(value="Reference track was recorded on: —")

        ref_fig = Figure(figsize=(6.2, 2.4), dpi=100)
        ref_ax_orig = ref_fig.add_subplot(1, 2, 1)
        ref_ax_trim = ref_fig.add_subplot(1, 2, 2)
        ref_canvas = FigureCanvasTkAgg(ref_fig, master=r)
        ref_canvas.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        def _apply_bandpass(x: np.ndarray, fs: int, low_hz: float, high_hz: float) -> np.ndarray:
            if x.size == 0:
                return x
            X = np.fft.rfft(x)
            freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
            mask = (freqs >= low_hz) & (freqs <= high_hz)
            X[~mask] = 0
            y = np.fft.irfft(X, n=len(x))
            return y.astype(np.float32, copy=False)

        def _plot_reference_waveforms(path: Path | None):
            ref_ax_orig.clear()
            ref_ax_trim.clear()
            ref_ax_orig.set_title("Reference - ORIGINAL")
            ref_ax_trim.set_title("Reference - TRIMMED")
            for ax in (ref_ax_orig, ref_ax_trim):
                ax.set_xlabel("Time (s)")
                ax.set_ylabel("Amplitude")
                ax.grid(True, axis="x", ls=":")

            if path and path.exists():
                x_ref, fs_ref = sf.read(path, dtype="float32", always_2d=False)
                if getattr(x_ref, "ndim", 1) == 2:
                    x_ref = x_ref.mean(axis=1)
                x_ref = normalize_mono(x_ref)
                x_trim = _apply_bandpass(x_ref, fs_ref, REF_CUTOFF_LOW_HZ, REF_CUTOFF_HIGH_HZ)
                t_ref = np.arange(len(x_ref), dtype=np.float32) / float(fs_ref if fs_ref else 1)
                ref_ax_orig.plot(t_ref, x_ref, linewidth=0.8)
                ref_ax_trim.plot(t_ref, x_trim, linewidth=0.8)

                stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                recorded_var.set(f"Reference track was recorded on: {stamp}")
            else:
                recorded_var.set("Reference track was recorded on: —")

            ref_canvas.draw_idle()

        ttk.Label(r, textvariable=cutoff_var, anchor="center").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(r, textvariable=ref_path_var, anchor="center").grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(r, textvariable=recorded_var, anchor="center").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        
        def _record_reference_here():
            """Record and save to assets/reference_master.wav using current duration."""
            fs_now = int(fs_var.get())
            dur_now = float(dur_var.get())
            # usar mismo dispositivo preferido que la app
            device_idx = self.input_device_index
            try:
                x = record_audio(dur_now, fs=fs_now, channels=1, device=device_idx)
                ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                out = (ASSETS_DIR / "reference_master.wav").resolve()
                sf.write(str(out), x, fs_now)
                ref_path_var.set(f"Reference track will be saved to: {out}")
                ref_var.set(str(out))
                _plot_reference_waveforms(out)
                messagebox.showinfo("Reference Track", f"Reference saved to:\n{out}")
            except Exception as e:
                messagebox.showerror("Reference Track", f"Recording failed:\n{e}")

        ttk.Label(r, text="(Uses the duration configured above)", anchor="center")\
            .grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        record_btn = tb.Button(r, text="Record Reference", bootstyle=PRIMARY, command=_record_reference_here)
        record_btn.grid(row=5, column=0, columnspan=2, pady=(0, 6))

        #----------------------------------------------------------------------------------------------------------------ventana "Evaluation"
        ev = ttk.Frame(nb); nb.add(ev, text="Evaluation")
        eval_var = tk.StringVar(value=self._cfg(["evaluation","level"], "Medium"))
        ttk.Label(ev, text="Criteria:").grid(row=0, column=0, sticky="w", pady=(6,2))
        eval_combo = ttk.Combobox(ev, textvariable=eval_var, values=["Low", "Medium", "High"], state="readonly", width=20)
        eval_combo.grid(row=0, column=1, sticky="w")


        #----------------------------------------------------------------------------------------------------------------ventana "Telemetry"
        t = ttk.Frame(nb); nb.add(t, text="Telemetry")
        host_var = tk.StringVar(value=self._cfg(["thingsboard","host"], "thingsboard.cloud"))
        port_var = tk.IntVar(value=int(self._cfg(["thingsboard","port"], 1883)))
        tls_var  = tk.BooleanVar(value=bool(self._cfg(["thingsboard","use_tls"], False)))
        token_var = tk.StringVar(value=self._cfg(["thingsboard","token"], ""))
        ttk.Label(t, text="Host:").grid(row=0, column=0, sticky="w", pady=(6,2))
        ttk.Entry(t, textvariable=host_var, width=24).grid(row=0, column=1, sticky="w")
        ttk.Label(t, text="Port:").grid(row=1, column=0, sticky="w", pady=(6,2))
        ttk.Entry(t, textvariable=port_var, width=10).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(t, text="Use TLS (8883)", variable=tls_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6,2))
        ttk.Label(t, text="Token:").grid(row=3, column=0, sticky="w", pady=(6,2))
        ttk.Entry(t, textvariable=token_var, width=40).grid(row=3, column=1, sticky="w")




        
        
        # Barra guardar/cancelar
        btns = ttk.Frame(frm); btns.pack(fill=X, pady=(10,0))
        def on_save():
            self._set_cfg(["reference","wav_path"], ref_var.get().strip())
            self._set_cfg(["oncalendar"], oncal_var.get().strip())
            self._set_cfg(["audio","fs"], int(fs_var.get()))
            self._set_cfg(["audio","duration_s"], float(dur_var.get()))
            selected_device = device_var.get()
            if ":" in selected_device:
                _, name = selected_device.split(":", 1)
                selected_name = name.strip()
            else:
                selected_name = selected_device.strip()
            self._set_cfg(["audio","preferred_input_name"], selected_name if selected_name != "No input devices detected" else "")
            self._set_cfg(["evaluation","level"], eval_var.get().strip())
            self._set_cfg(["thingsboard","host"], host_var.get().strip())
            self._set_cfg(["thingsboard","port"], int(port_var.get()))
            self._set_cfg(["thingsboard","use_tls"], bool(tls_var.get()))
            self._set_cfg(["thingsboard","token"], token_var.get().strip())
            save_config(self.cfg)

            # sincroniza cabecera
            self.fs.set(int(self._cfg(["audio","fs"], 48000)))
            self.duration.set(float(self._cfg(["audio","duration_s"], 10.0)))

            messagebox.showinfo(APP_NAME, "Settings saved.")
            w.destroy()

        tb.Button(btns, text="Save", bootstyle=PRIMARY, command=on_save).pack(side=RIGHT)
        tb.Button(btns, text="Cancel", bootstyle=SECONDARY, command=w.destroy).pack(side=RIGHT, padx=(0,6))

        try:
            w.grab_set()
            w.transient(self.root)
        except Exception:
            pass

    @ui_action
    def _run_once(self):
        # Lee SIEMPRE desde config (garantiza consistencia)
        fs  = int(self._cfg(["audio","fs"], 48000))
        dur = float(self._cfg(["audio","duration_s"], 10.0))
        self.last_fs = fs

        # 1) cargar referencia
        ref_path = Path(self._cfg(["reference","wav_path"], str(ASSETS_DIR/"reference_master.wav")))
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference file not found:\n{ref_path}")

        x_ref, fs_ref = sf.read(ref_path, dtype="float32", always_2d=False)
        if getattr(x_ref, "ndim", 1) == 2:
            x_ref = x_ref.mean(axis=1)
        x_ref = normalize_mono(x_ref)
        if fs_ref != fs:
            n_new = int(round(len(x_ref) * fs / fs_ref))
            x_idx = np.linspace(0, 1, len(x_ref))
            new_idx = np.linspace(0, 1, n_new)
            x_ref = np.interp(new_idx, x_idx, x_ref).astype(np.float32)

        # 2) grabar muestra
        x_cur = record_audio(dur, fs=fs, channels=1, device=self.input_device_index)

        # 3) analizar
        res = analyze_pair(x_ref, x_cur, fs)
        self._set_eval(res["overall"] == "PASSED")

        # 4) beeps/segments para JSON
        self.ref_markers = detect_beeps(x_ref, fs)
        self.cur_markers = detect_beeps(x_cur, fs)
        self.ref_segments = build_segments(x_ref, fs, self.ref_markers)
        self.cur_segments = build_segments(x_cur, fs, self.cur_markers)

        # 5) dibujar ondas
        self.last_ref, self.last_cur = x_ref, x_cur
        self._clear_waves()
        self._plot_wave(self.ax_ref, x_ref, fs)
        self._plot_wave(self.ax_cur, x_cur, fs)
        self.canvas.draw_idle()

        # 6) nombre de la prueba (no editable)
        self.test_name.set(datetime.now().strftime("Test_%Y-%m-%d_%H-%M-%S"))

        # 7) exportar y enviar
        payload = build_json_payload(
            fs, res, [], self.ref_markers, self.cur_markers,
            self.ref_segments, self.cur_segments, None, None
        )
        out = EXPORT_DIR / f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        sent = False
        host = self._cfg(["thingsboard","host"], "thingsboard.cloud")
        port = int(self._cfg(["thingsboard","port"], 1883))
        token = self._cfg(["thingsboard","token"], "")
        use_tls = bool(self._cfg(["thingsboard","use_tls"], False))
        if token:
            sent = send_json_to_thingsboard(payload, host, port, token, use_tls)

        self._set_messages([
            "The test " + ("passed." if res["overall"] == "PASSED" else "failed."),
            f"JSON: {out}",
            ("Results sent to ThingsBoard." if sent else "Results were not sent to ThingsBoard.")
        ])
        messagebox.showinfo(APP_NAME, f"Analysis complete.\nJSON: {out}")


# -------------------- main --------------------
def main():
    root = tb.Window(themename="flatly")
    app = AudioCinemaGUI(root)
    root.geometry("1020x640"); root.minsize(900,600)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
