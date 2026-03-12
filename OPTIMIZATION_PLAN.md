# Optimierungsplan für BPM Changer

## 1) Ist-Zustand (Kernfunktion)
Die Kernfunktion `change_bpm(...)` funktioniert grundsätzlich, hat aber mehrere technische Schwächen, die die Audioqualität direkt beeinflussen:

- **Tempo-Faktor basiert auf unsicherer BPM-Schätzung** ohne Plausibilitätsprüfung oder Fallback-Strategie.
- **Sample-Handling ist auf `int16` festgelegt**, wodurch Formate mit anderer Bit-Tiefe oder Float-Daten unpräzise verarbeitet werden.
- **Stereo-Handling erfolgt kanalweise unabhängig**, was bei manchen Tracks Artefakte oder Instabilität in der Stereobühne verursachen kann.
- **Fester Gain-Boost (+6 dB)** erhöht Clipping-Risiko und kann den Loudness-Eindruck verschlechtern.
- **MP3-Re-Encoding als einziger Output-Pfad** führt zu zusätzlichem Qualitätsverlust bei wiederholter Verarbeitung.

---

## 2) Zielbild (qualitativ deutlich bessere Kernfunktion)
Die Qualität soll in drei Dimensionen messbar besser werden:

1. **Tempo-Genauigkeit** (Output-BPM ist stabil nahe Ziel-BPM)
2. **Audio-Treue** (weniger Artefakte, kein unkontrolliertes Clipping, bessere Transienten)
3. **Robustheit** (funktioniert verlässlich für Mono/Stereo, verschiedene Samplerates, verschiedene Musikstile)

### Konkrete Qualitätsziele (Akzeptanzkriterien)
- Output-BPM liegt bei Testmaterial innerhalb von **±1.0 BPM** vom Ziel.
- True Peak im Output bleibt unter **-1 dBTP**.
- Keine unhandled Exceptions für Standardfälle (Mono/Stereo, 44.1/48 kHz, kurze und lange Dateien).
- Subjektive Hörtests auf Referenz-Playlist: deutlich weniger „Flanger/Chirping“-Artefakte bei ±15% Tempoänderung.

---

## 3) Priorisierter Umsetzungsplan

## Phase A — Schnell wirksame Qualitätsverbesserungen (1–2 Tage)
1. **Robuste BPM-Erkennung einführen**
   - Mehrere Schätzläufe (z. B. unterschiedliche `hop_length`/`start_bpm`) und Medianbildung.
   - Plausibilitätsfenster (z. B. 60–200 BPM) plus Halb-/Doppeltempo-Korrektur.
   - Fallback: manueller Override, wenn Confidence niedrig.

2. **Audio-Ein-/Ausgabe vereinheitlichen (float32 intern)**
   - Einheitliche interne Verarbeitung in `float32` statt direkter `int16`-Annahmen.
   - Klare Channel-Shape-Konvention (`[channels, samples]`).

3. **Clipping-sichere Ausgabe statt pauschalem +6 dB Gain**
   - Gain normalisieren auf Ziel-Peak (z. B. -1 dBFS), optional zusätzlicher Limiter.
   - In UI optionaler „Auto-Loudness“-Schalter statt hartem Boost.

**Erwarteter Effekt:** Sofort weniger Verzerrung/Clipping, stabilere Zielgeschwindigkeit.

## Phase B — Algorithmische Kernverbesserung (2–4 Tage)
4. **Time-Stretch-Backend austauschbar machen**
   - Aktuell: `librosa.effects.time_stretch`.
   - Ergänzen: optionales hochwertigeres Backend (z. B. Rubber Band CLI/Bibliothek, falls vorhanden).
   - A/B-Auswahl pro Datei im UI („Qualität“ vs. „Geschwindigkeit“).

5. **Stereo-Kohärenz verbessern**
   - Statt komplett separater Kanalverarbeitung: Mid/Side-Strategie oder gekoppelte Parameter.
   - Ziel: stabilere Räumlichkeit, weniger Kanal-Differenzartefakte.

6. **Grenzfälle für extreme Raten absichern**
   - Rate-Limits (z. B. 0.75–1.35 für „HQ-Modus“), außerhalb Warnung.
   - Optional zweistufiges Stretching bei Extremwerten zur Artefaktreduktion.

**Erwarteter Effekt:** Deutlich bessere Klangqualität bei realen Musiktracks, vor allem bei größerer BPM-Abweichung.

## Phase C — Qualitätssicherung & Messbarkeit (2–3 Tage)
7. **Automatisierte Audio-Regressionstests aufbauen**
   - Kleine Referenzdaten (drums, vocal-lastig, dichte Mixe).
   - Metriken: BPM-Fehler, Peak, RMS/LUFS (optional), Laufzeit.

8. **Golden-Master-Vergleich**
   - Definierte Testfälle + erwartete Metrikgrenzen.
   - CI-Check, der Qualitätsverschlechterungen früh erkennt.

9. **Strukturiertes Fehler-Logging**
   - Statt verstreutem Textlog: pro Job ID, Input-Format, erkannte BPM, Ziel-BPM, Rate, Output-Metriken.

**Erwarteter Effekt:** Nachhaltig reproduzierbare Qualität statt nur „gefühlt besser“.

---

## 4) Empfohlene Refaktorierung der Code-Struktur
Zur langfristigen Wartbarkeit sollte die Logik aufgeteilt werden:

- `audio_io.py` – Laden/Speichern, Formatkonvertierung
- `bpm_detection.py` – BPM-Erkennung + Confidence
- `time_stretch.py` – Backend-Abstraktion (librosa/rubberband)
- `loudness.py` – Peak/Loudness-Normalisierung
- `pipeline.py` – Orchestrierung der Kernfunktion
- GUI bleibt in `bpm_changer.py`, ruft nur noch `pipeline.process(...)` auf

So wird die Kernfunktion testbar und unabhängig von Tkinter.

---

## 5) Detaillierter Implementierungsfahrplan (Sprint-Vorschlag)

### Sprint 1 (Quick Wins)
- BPM-Erkennung robust machen
- `float32` Pipeline einführen
- Clipping-sichere Exportlogik
- Basis-Unit-Tests für Kanalformen und Rate-Berechnung

### Sprint 2 (Qualität)
- Stretch-Backend abstrahieren
- Optional Rubber Band integrieren
- Stereo-Kohärenz verbessern
- UI: Qualitätsmodus ergänzen

### Sprint 3 (Stabilität/Produktreife)
- Audio-Regressionstests + CI
- Verbesserte Logs + Fehlermeldungen
- Performance-Profiling und ggf. Caching

---

## 6) Risikoanalyse
- **Abhängigkeit von externem Tool (Rubber Band):** optional halten, sauberer Fallback auf librosa.
- **Subjektive Klangbewertung:** mit objektiven Metriken (BPM, Peak, ggf. LUFS) flankieren.
- **Performance vs. Qualität:** im UI explizit als Modus auswählbar machen.

---

## 7) Definition of Done (DoD)
Eine Optimierungsrunde gilt als abgeschlossen, wenn:

- Ziel-BPM-Toleranz eingehalten wird.
- Kein systematisches Clipping mehr auftritt.
- Bei Referenztracks hörbar weniger Artefakte auftreten.
- Regressionstests in CI grün sind.
- Nutzer in der GUI zwischen mindestens zwei Qualitätsprofilen wählen kann.

---

## 8) Sofort umsetzbare nächste 3 Schritte
1. `change_bpm` auf `float32`-Pipeline umstellen und festen +6 dB Boost entfernen.
2. BPM-Erkennung mit Plausibilitätscheck + Halb-/Doppeltempo-Korrektur ergänzen.
3. Einfache objektive Post-Checks implementieren (Peak, geschätzte Output-BPM) und im UI anzeigen.
