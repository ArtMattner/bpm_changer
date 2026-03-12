import os
import platform
import shutil
import sys
import threading
import time
from dataclasses import dataclass

import librosa
import numpy as np
import tkinter as tk
from pydub import AudioSegment
from tkinter import filedialog, messagebox, ttk


SUPPORTED_INPUT_EXTENSIONS = (
    "*.mp3", "*.wav", "*.flac", "*.ogg", "*.m4a", "*.aac", "*.wma", "*.aiff", "*.aif", "*.opus"
)

EXPORT_FORMATS = {
    "MP3 (.mp3)": {"ext": ".mp3", "format": "mp3", "codec": None, "bitrate": "320k"},
    "WAV (.wav)": {"ext": ".wav", "format": "wav", "codec": None, "bitrate": None},
    "FLAC (.flac)": {"ext": ".flac", "format": "flac", "codec": None, "bitrate": None},
    "OGG Vorbis (.ogg)": {"ext": ".ogg", "format": "ogg", "codec": "libvorbis", "bitrate": "256k"},
    "AAC (.m4a)": {"ext": ".m4a", "format": "ipod", "codec": "aac", "bitrate": "256k"},
}


@dataclass
class AudioMeta:
    sample_rate: int
    channels: int
    duration_s: float
    size_mb: float
    estimated_bpm: float


def check_ffmpeg_dependencies():
    ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    ffprobe_exe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"

    ffmpeg_path = shutil.which(ffmpeg_exe)
    ffprobe_path = shutil.which(ffprobe_exe)

    if not ffmpeg_path or not ffprobe_path:
        messagebox.showerror(
            "Fehlende Abhängigkeit",
            f"{ffmpeg_exe} und/oder {ffprobe_exe} wurden nicht gefunden.\n"
            "Bitte ffmpeg installieren und in den PATH aufnehmen.",
        )
        sys.exit(1)


def _segment_to_float_array(audio: AudioSegment) -> np.ndarray:
    sample_width = audio.sample_width
    if sample_width == 1:
        dtype = np.int8
        scale = 128.0
    elif sample_width == 2:
        dtype = np.int16
        scale = 32768.0
    elif sample_width == 4:
        dtype = np.int32
        scale = 2147483648.0
    else:
        audio = audio.set_sample_width(2)
        dtype = np.int16
        scale = 32768.0

    samples = np.frombuffer(audio.raw_data, dtype=dtype).astype(np.float32)
    if audio.channels > 1:
        samples = samples.reshape((-1, audio.channels)).T
    return samples / scale


def _float_array_to_segment(y: np.ndarray, sr: int) -> AudioSegment:
    y = np.clip(y, -1.0, 1.0)
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y * (0.89 / peak)

    pcm = (y * 32767).astype(np.int16)
    if y.ndim == 1:
        raw = pcm.tobytes()
        channels = 1
    else:
        raw = pcm.T.flatten().tobytes()
        channels = y.shape[0]

    return AudioSegment(data=raw, sample_width=2, frame_rate=sr, channels=channels)


def estimate_bpm(y: np.ndarray, sr: int) -> float:
    mono = y.mean(axis=0) if y.ndim == 2 else y
    if len(mono) < 4096:
        raise ValueError("Audio ist zu kurz für BPM-Erkennung.")

    candidates = []
    configs = [(512, 90), (512, 120), (1024, 120), (1024, 140)]
    for hop_length, start_bpm in configs:
        bpm, _ = librosa.beat.beat_track(y=mono, sr=sr, hop_length=hop_length, start_bpm=start_bpm)
        value = float(bpm.item() if hasattr(bpm, "item") else bpm)
        if 40 <= value <= 260:
            candidates.append(value)

    if not candidates:
        raise ValueError("BPM konnte nicht robust geschätzt werden.")

    bpm = float(np.median(candidates))
    if bpm < 60:
        bpm *= 2
    elif bpm > 200:
        bpm /= 2
    return bpm


def change_bpm(input_path: str, output_path: str, target_bpm: float, export_profile: dict, progress_callback=None) -> float:
    audio = AudioSegment.from_file(input_path)
    sr = audio.frame_rate
    y = _segment_to_float_array(audio)

    original_bpm = estimate_bpm(y, sr)
    if progress_callback:
        progress_callback(25)

    rate = target_bpm / original_bpm
    if rate <= 0:
        raise ValueError("Ungültige Ziel-BPM.")

    if y.ndim == 2:
        stretched = np.array([librosa.effects.time_stretch(y=channel, rate=rate) for channel in y])
    else:
        stretched = librosa.effects.time_stretch(y=y, rate=rate)

    if progress_callback:
        progress_callback(70)

    out_segment = _float_array_to_segment(stretched, sr)

    export_kwargs = {"format": export_profile["format"]}
    if export_profile["codec"]:
        export_kwargs["codec"] = export_profile["codec"]
    if export_profile["bitrate"]:
        export_kwargs["bitrate"] = export_profile["bitrate"]

    out_segment.export(output_path, **export_kwargs)

    if progress_callback:
        progress_callback(100)

    return original_bpm


def analyze_audio(path: str) -> AudioMeta:
    audio = AudioSegment.from_file(path)
    y = _segment_to_float_array(audio)
    bpm = estimate_bpm(y, audio.frame_rate)
    return AudioMeta(
        sample_rate=audio.frame_rate,
        channels=audio.channels,
        duration_s=len(audio) / 1000.0,
        size_mb=os.path.getsize(path) / (1024 * 1024),
        estimated_bpm=bpm,
    )


class BPMChangerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("BPM Changer Pro")
        self.master.geometry("860x620")
        self.master.minsize(820, 580)
        self.file_path = None

        self._setup_theme()
        self._build_ui()

    def _setup_theme(self):
        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background="#151922")
        style.configure("Card.TFrame", background="#1e2430")
        style.configure("Title.TLabel", background="#151922", foreground="#f3f7ff", font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#151922", foreground="#a8b2c6", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#1e2430", foreground="#f3f7ff", font=("Segoe UI", 11, "bold"))
        style.configure("CardText.TLabel", background="#1e2430", foreground="#d5dceb", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        self.master.configure(bg="#151922")

    def _build_ui(self):
        root = ttk.Frame(self.master, style="App.TFrame", padding=16)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="BPM Changer Pro", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Konvertiere Audio in Ziel-BPM – mit Multi-Format Import/Export.", style="Sub.TLabel").pack(anchor="w", pady=(0, 14))

        content = ttk.Frame(root, style="App.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        left = ttk.Frame(content, style="Card.TFrame", padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right = ttk.Frame(content, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        content.rowconfigure(0, weight=1)

        # Input card
        ttk.Label(left, text="1) Input", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Button(left, text="Audio auswählen", style="Accent.TButton", command=self.select_file).grid(row=1, column=0, sticky="w")

        self.filename_label = ttk.Label(left, text="Keine Datei ausgewählt", style="CardText.TLabel")
        self.filename_label.grid(row=2, column=0, sticky="w", pady=(10, 4))

        self.fileinfo_label = ttk.Label(left, text="", style="CardText.TLabel")
        self.fileinfo_label.grid(row=3, column=0, sticky="w")

        # Conversion card
        ttk.Label(left, text="2) Konvertierung", style="CardTitle.TLabel").grid(row=4, column=0, sticky="w", pady=(20, 10))

        ttk.Label(left, text="Ziel-BPM", style="CardText.TLabel").grid(row=5, column=0, sticky="w")
        self.bpm_entry = ttk.Entry(left)
        self.bpm_entry.insert(0, "128")
        self.bpm_entry.grid(row=6, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(left, text="Export-Format", style="CardText.TLabel").grid(row=7, column=0, sticky="w")
        self.export_format = tk.StringVar(value=list(EXPORT_FORMATS.keys())[0])
        self.export_combo = ttk.Combobox(
            left,
            textvariable=self.export_format,
            values=list(EXPORT_FORMATS.keys()),
            state="readonly",
        )
        self.export_combo.grid(row=8, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(left, text="Dateiname (optional)", style="CardText.TLabel").grid(row=9, column=0, sticky="w")
        self.filename_override = ttk.Entry(left)
        self.filename_override.grid(row=10, column=0, sticky="ew", pady=(4, 14))

        ttk.Button(left, text="Konvertierung starten", style="Accent.TButton", command=self.run_conversion).grid(row=11, column=0, sticky="ew")

        left.columnconfigure(0, weight=1)

        # Output card
        ttk.Label(right, text="3) Ausgabe", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))

        ttk.Label(right, text="Zielordner", style="CardText.TLabel").grid(row=1, column=0, sticky="w")
        path_row = ttk.Frame(right, style="Card.TFrame")
        path_row.grid(row=2, column=0, sticky="ew", pady=(4, 14))
        path_row.columnconfigure(0, weight=1)

        self.save_dir = tk.StringVar(value="")
        ttk.Entry(path_row, textvariable=self.save_dir).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(path_row, text="Ordner", command=self.select_save_folder).grid(row=0, column=1)

        self.progress = ttk.Progressbar(right, orient="horizontal", mode="determinate", length=350)
        self.progress.grid(row=3, column=0, sticky="ew")

        self.percent_label = ttk.Label(right, text="0%", style="CardText.TLabel")
        self.percent_label.grid(row=4, column=0, sticky="w", pady=(6, 12))

        self.status_label = ttk.Label(right, text="Status: Bereit", style="CardText.TLabel")
        self.status_label.grid(row=5, column=0, sticky="w")

        self.outputinfo_label = ttk.Label(right, text="", style="CardText.TLabel")
        self.outputinfo_label.grid(row=6, column=0, sticky="w", pady=(10, 0))

        ttk.Label(
            right,
            text="Unterstützte Inputs: MP3, WAV, FLAC, OGG, M4A, AAC, WMA, AIFF, OPUS",
            style="Sub.TLabel",
        ).grid(row=7, column=0, sticky="w", pady=(24, 0))

        right.columnconfigure(0, weight=1)

    def select_save_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_dir.set(folder)

    def select_file(self):
        filetypes = [("Audio Dateien", " ".join(SUPPORTED_INPUT_EXTENSIONS)), ("Alle Dateien", "*.*")]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if not path:
            return

        self.file_path = path
        self.filename_label.config(text=os.path.basename(path))

        try:
            meta = analyze_audio(path)
            self.fileinfo_label.config(
                text=(
                    f"{meta.estimated_bpm:.2f} BPM | {meta.duration_s:.1f}s | "
                    f"{meta.sample_rate} Hz | {meta.channels} Kanal/Kanäle | {meta.size_mb:.2f} MB"
                )
            )
            self.status_label.config(text="Status: Audio erfolgreich analysiert")
            if not self.filename_override.get().strip():
                base = os.path.splitext(os.path.basename(path))[0]
                self.filename_override.delete(0, tk.END)
                self.filename_override.insert(0, f"{base}_BPM-CHANGER")
        except Exception as exc:
            self.fileinfo_label.config(text="Fehler bei der Audioanalyse")
            self.status_label.config(text="Status: Analyse fehlgeschlagen")
            messagebox.showerror("Fehler", f"Datei konnte nicht gelesen werden:\n{exc}")

    def _set_progress(self, value: int):
        self.progress["value"] = value
        self.percent_label.config(text=f"{int(value)}%")
        self.master.update_idletasks()

    def run_conversion(self):
        if not self.file_path:
            messagebox.showerror("Fehler", "Bitte zuerst eine Audio-Datei auswählen.")
            return

        try:
            target_bpm = float(self.bpm_entry.get())
            if target_bpm <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fehler", "Bitte eine gültige Ziel-BPM eingeben (> 0).")
            return

        selected_profile = EXPORT_FORMATS[self.export_format.get()]

        target_dir = self.save_dir.get().strip() or os.path.dirname(self.file_path)
        os.makedirs(target_dir, exist_ok=True)

        base_name = self.filename_override.get().strip() or os.path.splitext(os.path.basename(self.file_path))[0]
        if base_name.lower().endswith(selected_profile["ext"]):
            final_name = base_name
        else:
            final_name = f"{base_name}{selected_profile['ext']}"

        output_path = os.path.join(target_dir, final_name)

        self._set_progress(0)
        self.status_label.config(text="Status: Verarbeitung läuft …")
        self.outputinfo_label.config(text="")

        def worker():
            start = time.time()
            try:
                original_bpm = change_bpm(
                    input_path=self.file_path,
                    output_path=output_path,
                    target_bpm=target_bpm,
                    export_profile=selected_profile,
                    progress_callback=lambda p: self.master.after(0, self._set_progress, p),
                )
                duration = time.time() - start
                size_mb = os.path.getsize(output_path) / (1024 * 1024)

                self.master.after(0, lambda: self.status_label.config(text=f"Status: Fertig in {duration:.1f}s"))
                self.master.after(0, lambda: self.outputinfo_label.config(text=f"{os.path.basename(output_path)} | {size_mb:.2f} MB"))
                self.master.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Erfolg",
                        f"Original BPM: {original_bpm:.2f}\nZiel BPM: {target_bpm:.2f}\nGespeichert unter:\n{output_path}",
                    ),
                )
            except Exception as exc:
                self.master.after(0, lambda: self.status_label.config(text="Status: Fehler bei Verarbeitung"))
                self.master.after(0, lambda: messagebox.showerror("Fehler", str(exc)))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    check_ffmpeg_dependencies()
    root = tk.Tk()
    app = BPMChangerApp(root)
    root.mainloop()
