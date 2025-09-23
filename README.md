# BPM Changer
This little piece of software lets you change the BPM of an existing MP3 without altering the pitch. The latest version also offers a couple of quality-focused enhancements, so you can export lossless files or clean up the audio before saving it under a new name.

## Features
- Change the tempo (BPM) of an MP3 while preserving the pitch
- Export either as MP3 (320 kbit/s), WAV or FLAC
- Optional loudness normalisation and noise reduction
- Gentle bass and treble controls to polish the output

## Steps to install
1. Install `ffmpeg`/`ffprobe` on your system and ensure the executables are available via the `PATH`.
2. Install the Python dependencies listed in `requirements.txt` (e.g. `pip install -r requirements.txt`).
3. Start the application with `python bpm_changer.py`.
