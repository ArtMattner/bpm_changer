# BPM Changer Pro

Desktop-App zum Ändern der BPM von Audiodateien, ohne die Tonhöhe zu verändern (Time-Stretch).

## Features
- Moderne Tkinter/ttk UI mit klaren Bereichen für Input, Konvertierung und Output
- Multi-Format **Import**: MP3, WAV, FLAC, OGG, M4A, AAC, WMA, AIFF, OPUS
- Multi-Format **Export**: MP3, WAV, FLAC, OGG, AAC (M4A)
- Robustere BPM-Schätzung (Median über mehrere Schätzläufe)
- Clipping-sicherer Output (automatische Peak-Begrenzung)

## Installation
1. `ffmpeg` und `ffprobe` installieren und in den PATH aufnehmen.
2. Python-Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
3. App starten:
   ```bash
   python bpm_changer.py
   ```

## Hinweise
- Für manche Codecs hängt die Verfügbarkeit vom installierten FFmpeg-Build ab.
- Sehr extreme BPM-Änderungen können bei jedem Time-Stretch-Verfahren hörbare Artefakte erzeugen.
