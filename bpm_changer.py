import librosa
import soundfile as sf
from pydub import AudioSegment
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import time
from tempfile import NamedTemporaryFile
import numpy as np
from PIL import Image, ImageTk
import shutil
import sys
import platform

# Prüfe ffmpeg/ffprobe-Abhängigkeiten
def check_ffmpeg_dependencies():
    system = platform.system()
    if system == "Windows":
        ffmpeg_exe = "ffmpeg.exe"
        ffprobe_exe = "ffprobe.exe"
    else:
        ffmpeg_exe = "ffmpeg"
        ffprobe_exe = "ffprobe"

    ffmpeg_path = shutil.which(ffmpeg_exe)
    ffprobe_path = shutil.which(ffprobe_exe)

    log_path = os.path.join(os.getcwd(), "bpm_changer_log.txt")
    try:
        with open(log_path, "a") as f:
            f.write(f"ffmpeg path: {ffmpeg_path}\n")
            f.write(f"ffprobe path: {ffprobe_path}\n")
    except Exception as e:
        print(f"Fehler beim Schreiben des Logs: {e}")

    if not ffmpeg_path or not ffprobe_path:
        message = (
            f"Fehler: {ffmpeg_exe} und/oder {ffprobe_exe} sind nicht installiert oder nicht im PATH verfügbar.\n\n"
            "Bitte installiere ffmpeg und stelle sicher, dass die Befehle im Systempfad verfügbar sind."
        )
        messagebox.showerror("Abhängigkeit fehlt", message)
        sys.exit(1)


# Logging function for environment info
def log_environment_info():
    try:
        log_path = os.path.join(os.getcwd(), "bpm_changer_log.txt")
        with open(log_path, "w") as f:
            f.write(f"Executable path: {sys.executable}\n")
            f.write(f"__file__: {__file__}\n")
            f.write(f"Current working directory: {os.getcwd()}\n")
            f.write(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Not set')}\n")
    except Exception as e:
        print(f"Fehler beim Schreiben des Logs: {e}")

def change_bpm(input_path, output_path, target_bpm, progress_callback=None):

    audio = AudioSegment.from_file(input_path)
    sr = audio.frame_rate
    samples = np.frombuffer(audio.raw_data, dtype=np.int16).astype(np.float32)
    if audio.channels == 2:
        samples = np.array(samples.reshape((-1, 2)).T)
    y = samples / 32768.0
    original_bpm, _ = librosa.beat.beat_track(y=y, sr=sr, units='frames', hop_length=512, tightness=100, start_bpm=120, trim=False, sparse=False)
    if isinstance(original_bpm, (np.ndarray, list)):
        original_bpm = float(np.array(original_bpm).flatten()[0])
    else:
        original_bpm = float(original_bpm)
    if progress_callback: progress_callback(20)

    rate = target_bpm / original_bpm
    # Stretch each channel separately if stereo, then normalize output
    if y.ndim == 2:
        y_stretched = np.array([
            librosa.effects.time_stretch(y[i], rate=rate)
            for i in range(y.shape[0])
        ])
    else:
        y_stretched = librosa.effects.time_stretch(y, rate=rate)
    y_stretched = y_stretched * 0.95
    if progress_callback: progress_callback(50)

    # Konvertiere gestretchte Audiodaten in int16
    y_stretched = np.clip(y_stretched, -1.0, 1.0)
    if y_stretched.ndim == 1:
        pcm = (y_stretched * 32767).astype(np.int16)
        audio_out = AudioSegment(
            pcm.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=1
        )
    else:
        pcm = (y_stretched * 32767).astype(np.int16).T.flatten()
        audio_out = AudioSegment(
            pcm.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=y_stretched.shape[0]
        )
    louder = audio_out.apply_gain(6)
    louder.export(output_path, format="mp3", bitrate="320k")
    output_size = os.path.getsize(output_path) / (1024 * 1024)
    if progress_callback:
        progress_callback(95)

    if progress_callback: progress_callback(100)
    return original_bpm

class BPMChangerApp:
    def __init__(self, master):
        self.master = master
        self.master.configure(bg='black')
        # Load background image relative to script location, works on Windows and others
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.bg_image_path = os.path.join(base_dir, "assets", "A_vibrant_digital_illustration_in_a_futuristic_spa.png")
        try:
            self.original_bg_image = Image.open(self.bg_image_path)
            original_width, original_height = self.original_bg_image.size
            max_width, max_height = 720, 680
            scale_w = max_width / original_width
            scale_h = max_height / original_height
            scale = min(scale_w, scale_h, 1.0)
            scaled_width = int(original_width * scale)
            scaled_height = int(original_height * scale)
            self.bg_photo = ImageTk.PhotoImage(self.original_bg_image.resize((scaled_width, scaled_height), Image.LANCZOS))
            master.geometry(f"{scaled_width}x{scaled_height}")
            master.minsize(scaled_width, scaled_height)
            self.bg_label = tk.Label(master, image=self.bg_photo)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"Fehler beim Laden des Hintergrundbilds: {e}")
        master.title("Captain's BPM Changer")
        master.resizable(True, True)

        self.file_path = None

        tk.Label(master, text="1. Wähle eine MP3-Datei:").pack(pady=5)
        tk.Button(master, text="Datei auswählen", command=self.select_file).pack()

        self.filename_label = tk.Label(master, text="Keine Datei ausgewählt", fg="gray")
        self.filename_label.pack()
        self.fileinfo_label = tk.Label(master, text="", fg="gray")
        self.fileinfo_label.pack()

        tk.Label(master, text="2. Ziel-BPM eingeben:").pack(pady=10)
        self.bpm_entry = tk.Entry(master)
        self.bpm_entry.pack()

        tk.Label(master, text="3. Konvertieren:").pack(pady=10)
        tk.Button(master, text="Start", command=self.run_conversion).pack()

        tk.Label(master, text="4. Speicherort (optional):").pack(pady=5)
        self.save_dir = tk.StringVar(value="")
        self.save_entry = tk.Entry(master, textvariable=self.save_dir, width=40)
        self.save_entry.pack()
        tk.Button(master, text="Ordner wählen", command=self.select_save_folder).pack(pady=2)

        tk.Label(master, text="Dateiname (ohne .mp3):").pack(pady=5)
        self.filename_override = tk.StringVar()
        self.filename_entry = tk.Entry(master, textvariable=self.filename_override, width=40)
        self.filename_entry.pack()

        frame = tk.Frame(master)
        frame.pack(pady=15)
        self.progress = ttk.Progressbar(frame, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(side="left")
        self.percent_label = tk.Label(frame, text="0%")
        self.percent_label.pack(side="left", padx=10)

        self.status_label = tk.Label(master, text="Status: Bereit", fg="blue")
        self.status_label.pack()

        self.outputinfo_label = tk.Label(master, text="", fg="gray")
        self.outputinfo_label.pack()

        # self.fileinfo_label is now packed above, directly after filename_label

        for widget in master.winfo_children():
            widget.lift()

    def select_save_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_dir.set(folder)

    def select_file(self):

        self.file_path = filedialog.askopenfilename(filetypes=[("MP3 Dateien", "*.mp3")])
        if self.file_path:
            self.filename_label.config(text=os.path.basename(self.file_path))
            try:
                audio = AudioSegment.from_file(self.file_path)
                sr = audio.frame_rate
                samples = np.frombuffer(audio.raw_data, dtype=np.int16).astype(np.float32)
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2))
                    samples = samples.mean(axis=1)
                y = samples / 32768.0
                if y is None or len(y) < 2048:
                    raise ValueError("Audio zu kurz oder leer.")
                bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
                bpm = float(bpm.item() if hasattr(bpm, "item") else bpm)
                size = os.path.getsize(self.file_path) / (1024 * 1024)
                self.fileinfo_label.config(text=f"BPM: {bpm:.2f}, Größe: {size:.2f} MB")
                self.status_label.config(text="Status: BPM erkannt", fg="green")
                if not self.filename_override.get().strip():
                    default_name = os.path.splitext(os.path.basename(self.file_path))[0] + "_BPM-CHANGER"
                    self.filename_override.set(default_name)
            except Exception as e:
                self.fileinfo_label.config(text="Fehler beim BPM-Auslesen!", fg="red")
                self.status_label.config(text="Status: Fehler beim Erkennen", fg="red")
                messagebox.showerror("Fehler", f"BPM konnte nicht erkannt werden:\n{str(e)}")

    def run_conversion(self):
        if not self.file_path:
            messagebox.showerror("Fehler", "Bitte wähle eine MP3-Datei aus.")
            return

        try:
            target_bpm = float(self.bpm_entry.get())
        except ValueError:
            messagebox.showerror("Fehler", "Bitte gib eine gültige BPM-Zahl ein.")
            return

        self.progress["value"] = 0
        self.status_label.config(text="Status: Verarbeitung läuft...", fg="darkorange")

        def task():
            start_time = time.time()
            try:
                if self.filename_override.get().strip():
                    base_name = self.filename_override.get().strip() + ".mp3"
                else:
                    base_name = os.path.basename(os.path.splitext(self.file_path)[0]) + f"_{int(target_bpm)}bpm.mp3"
                target_dir = self.save_dir.get() if self.save_dir.get() else os.path.dirname(self.file_path)
                output_path = os.path.join(target_dir, base_name)
                original_size = os.path.getsize(self.file_path) / (1024 * 1024)
                original_bpm = change_bpm(self.file_path, output_path, target_bpm, self.update_progress)
                output_size = os.path.getsize(output_path) / (1024 * 1024)
                duration = time.time() - start_time

                self.status_label.config(
                    text=f"Fertig in {duration:.1f}s", fg="green"
                )
                self.outputinfo_label.config(
                    text=f"{os.path.basename(output_path)} ({output_size:.2f} MB)"
                )
                messagebox.showinfo("Fertig", f"Original BPM: {original_bpm:.2f}\nGröße: {output_size:.2f} MB\nGespeichert als:\n{output_path}")
            except Exception as e:
                self.status_label.config(text="Fehler beim Verarbeiten!", fg="red")
                messagebox.showerror("Fehler", f"{str(e)}")

        threading.Thread(target=task).start()

    def update_progress(self, percent):
        self.progress["value"] = percent
        self.percent_label.config(text=f"{int(percent)}%")
        self.master.update_idletasks()
        

if __name__ == "__main__":
    check_ffmpeg_dependencies()
    log_environment_info()
    root = tk.Tk()
    app = BPMChangerApp(root)
    root.mainloop()