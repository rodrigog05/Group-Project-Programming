"""Build the original 'Saudade do Tejo' acoustic guitar loop. No dependencies.

This is an original instrumental inspired by fado guitar phrasing, not a recording
or transcription of an existing song. Run once to rebuild the bundled WAV.
"""
from array import array
import math
from pathlib import Path
import random
import wave

RATE = 22050


def pluck(midi, seconds, bright=False):
    rng = random.Random(midi * 37 + int(bright))
    frequency = 440 * 2 ** ((midi - 69) / 12)
    length = max(2, round(RATE / frequency))
    ring = [rng.uniform(-1, 1) for _ in range(length)]
    result = array("f")
    damping = 0.995 if bright else 0.991
    previous = 0.0
    for index in range(round(seconds * RATE)):
        position = index % length
        sample = ring[position]
        ring[position] = damping * (sample + ring[(position + 1) % length]) * 0.5
        previous = previous * 0.22 + sample * 0.78
        attack = min(1, index / (RATE * 0.004))
        result.append(previous * attack * math.exp(-index / (RATE * (2.1 if bright else 1.5))))
    return result


def compose(path):
    pulse = 60 / 96 / 2
    bars = 32
    duration = bars * 6 * pulse
    left = array("f", [0.0]) * round(duration * RATE)
    right = array("f", [0.0]) * len(left)
    cache = {}

    def note(midi, at, level, pan=0, bright=False, length=2.0):
        key = midi, bright, length
        if key not in cache:
            cache[key] = pluck(midi, length, bright)
        start = round(at * RATE)
        for index, value in enumerate(cache[key]):
            target = (start + index) % len(left)
            left[target] += value * level * (1 - pan * 0.35)
            right[target] += value * level * (1 + pan * 0.35)

    # A minor, D minor, E dominant, A minor. Original answering phrases in 6/8.
    chords = ((45, (57, 60, 64)), (50, (57, 62, 65)), (40, (56, 59, 64)), (45, (57, 60, 64)))
    phrases = ((76, 74, 72, 71, 72, 69), (74, 77, 76, 74, 72, 71),
               (71, 68, 71, 74, 76, 74), (72, 71, 69, 68, 69, 69),
               (81, 79, 76, 74, 72, 76), (77, 76, 74, 72, 74, 77),
               (76, 74, 71, 68, 71, 74), (72, 71, 69, 76, 72, 69))
    for bar in range(bars):
        start = bar * 6 * pulse
        bass, chord = chords[bar % 4]
        note(bass, start, 0.28, -0.5, length=2.8)
        note(bass + 12, start + 3 * pulse, 0.18, -0.3)
        for beat, pitch_index in enumerate((0, 1, 2, 0, 2, 1)):
            note(chord[pitch_index], start + beat * pulse + 0.035, 0.18, -0.45)
        for beat, pitch in enumerate(phrases[bar % 8]):
            if bar % 8 == 7 and beat > 3:
                continue
            note(pitch, start + beat * pulse + 0.015, 0.22, 0.45, True)
            # Brief doubled-string responses give a bright Portuguese-guitar texture.
            if beat in (0, 3):
                note(pitch, start + beat * pulse + 0.070, 0.065, 0.7, True)
    # A short stereo room reflection, then gentle normalization for background use.
    delay = round(RATE * 0.083)
    for index in range(len(left)-1, delay-1, -1):
        left[index] += right[index-delay] * 0.13
        right[index] += left[index-delay] * 0.11
    peak = max(max(abs(v) for v in left), max(abs(v) for v in right), 1e-6)
    pcm = array("h")
    for index, (l, r) in enumerate(zip(left, right)):
        fade = min(1, index/(RATE*.12), (len(left)-1-index)/(RATE*.35))
        pcm.extend((round(l / peak * 15000 * fade), round(r / peak * 15000 * fade)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm.tobytes())
    return duration


if __name__ == "__main__":
    target = Path(__file__).parent / "assets" / "saudade_do_tejo.wav"
    print(f"Built {compose(target):.0f}s original guitar soundtrack: {target}")
