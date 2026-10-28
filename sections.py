#!/usr/bin/env python3
"""sections.py — cache/features.json -> cache/sections.json, and print the section map.

    .venv/bin/python sections.py

Copied from laser-beam-demo's sections.py. Boundaries are read off the features (novelty
peaks, bass dropouts, chroma repeats; each one's reason is kept in "why"), then snapped to
the nearest tracked beat within half a second, so every hard cut lands on a beat.
Word cues (CUES) are the moments a scene hits on a sung or spoken word; they are not
snapped. Clock ticks are the tick candidates in the intro and outro that sit on the
half-beat grid.

Drafted from a transcript of the song (faster-whisper medium.en, word timestamps, Oct 28;
the opening re-run in short overlapping windows, because the full pass ran 0:05-0:37 into one
segment); every sung section starts on its first sung word. Checked by the author, Oct 28.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(HERE, "cache", "features.json")
OUT = os.path.join(HERE, "cache", "sections.json")
TICK_ON_GRID = 0.05               # s from the half-beat grid
TICK_SECTIONS = set()            # no clock sample in this song: no tick sections

# (name, scene, start s, why): each start is the first sung word of the section, from the
# transcript, snapped to the nearest beat. Suno sang no Eratosthenes verse and no second
# chorus; the brief's verse-1 sieve rides chorus 1 ("the stations walk the line") and the
# 9 s break after it stands in for the guitar solo.
RAW = [
    ("intro",        "sieve",     0.0,    "fade-in from -48 dBFS, no voice"),
    ("prechorus",    "sieve",   5.20,   "'No one asked the survivors' (5.20)"),
    ("chorus1",      "sieve",    14.80,  "'It's light through the holes' (14.80)"),
    ("solo",         "strobe",   37.0,   "instrumental after 'never free' ends (35.94-~37), to 46.04"),
    ("verse2",       "legendre", 46.04,  "'The legendary Captain Ledger' (Legendre's ledger)"),
    ("verse3",       "lehmer",   77.24,  "'1933, the World's Fair'"),
    ("verse4",       "rsa",      106.52, "'Well, they rolled a lock in '77'"),
    ("bridge",       "lamps",    151.60, "'So I built my lamps on a laptop', after a 3.5 s gap"),
    ("tentimes",     "arms",     172.26, "'Ten times, not a hundred'; chroma best-fits +2..+5 semitones vs chorus 1 from here"),
    ("final_chorus", "finale",   183.78, "'It's light through the holes' (heard 'right through the hall')"),
    ("outro",        "outro",    213.22, "'The survivors of a sieve', after a 7 s instrumental"),
]
# (name, time s, why): word starts from the transcript, not snapped; scenes hit on these
CUES = [
    ("survivors",        7.10,   "pre-chorus 'survivors' ('No one asked' from 5.20): grey static"),
    ("known",            11.00,  "'They were known by what was missed' (11.00-13.60): the survivors glow"),
    ("stations",         17.80,  "chorus 1 'The stations walk the line' (17.80-18.84)"),
    ("every_gear",       19.74,  "chorus 1 'every gear in its own time'"),
    ("align",            22.32,  "chorus 1 'wait until they all align' ('align' 23.88)"),
    ("build_dark",       24.62,  "chorus 1 'You build the dark to find the bright'"),
    ("pay_see",          26.92, "chorus 1 'you pay before you see' ('pay' 27.80)"),
    ("light_holes1b",    29.68, "chorus 1 'It's light through the holes' (second time)"),
    ("never_free",       33.30,  "chorus 1 'and the holes were never free'"),
    ("abacus",           51.02,  "verse 2 'Plus and minus on an abacus'"),
    ("wander",           56.18,  "verse 2 'The signs began to wander'"),
    ("stray",            61.22,  "verse 2 'how far they can stray' ('stray' 65.66)"),
    ("selberg_wall",     66.18,  "verse 2 'Then Selberg found the wall'"),
    ("one_floor",        72.20,  "verse 2 'one floor from two' (72.20-73.34)"),
    ("cabinet",          81.38,  "verse 3 'a young man built a cabinet of gears'"),
    ("lamp_cell",        86.18,  "verse 3 'A lamp on one side, a cell on the other'"),
    ("windows",          96.48,  "verse 3 'And when the windows lined up once'"),
    ("shining",          99.04,  "verse 3 'the light came shining through': the flash"),
    ("wound_back",       101.54, "verse 3 'and Lehmer wound it back by hand' (heard 'led my wounded')"),
    ("read_found",       104.32, "verse 3 'to read what it had found': the factors"),
    ("lock_77",          106.88, "verse 4 'they rolled a lock in '77' ('77' 108.74)"),
    ("lifetimes",        111.36, "verse 4 'said it'd last ten thousand lifetimes long' (heard 'it lasts')"),
    ("volunteers",       115.74, "verse 4 'Then the volunteers came'"),
    ("machines",         117.54, "verse 4 'sixteen hundred machines'"),
    ("seventeen",        121.52, "verse 4 'and seventeen years along' (heard 'In')"),
    ("magic_words",      127.28, "verse 4 'The message read the magic words'"),
    ("ossifrage",        129.96, "verse 4 'squeamish ossifrage' (129.96-131.52)"),
    ("never_broke",      131.76, "verse 4 'They never broke the wall, they only paid its wage'"),
    ("shamir",           136.90, "verse 4 'Shamir dreamed of diodes': TWINKLE"),
    ("brightness",       141.84, "verse 4 'The brightness was the answer'"),
    ("darkness",         144.12, "verse 4 'and the darkness was the same' (to 147.52)"),
    ("watts",            157.68, "bridge 'A meter for the watts'"),
    ("light_meter",      159.58, "bridge 'and a meter for the light'"),
    ("wrong",            162.24, "bridge 'I was wrong in the open'"),
    ("three_point_four", 167.24, "bridge 'The formula said three-point-four' ('3.4' 168.60-169.06+)"),
    ("one_point_four",   169.76, "bridge 'the primes came back around'"),
    ("ten_times",        172.26, "hook 'Ten times, not a hundred': the lift (the key rises here)"),
    ("reach_out",        174.24, "hook 'reach out'"),
    ("not_too_far",      175.48, "hook 'but not too far' (to 176.50)"),
    ("center_dark",      177.18, "hook 'and the center stays dark'"),
    ("balanced",         179.84, "hook 'where the balanced numbers are' (to ~183)"),
    ("stations2",        187.98, "final chorus 'The stations walk the line'"),
    ("every_gear2",      190.00, "final chorus 'every gear in its own time'"),
    ("align2",           192.76, "final chorus 'wait until they all align'"),
    ("build_dark2",      194.96, "final chorus 'You build the dark to find the bright'"),
    ("pay_see2",         197.48, "final chorus 'you pay before you see'"),
    ("light_holes2",     200.32, "final chorus 'It's light through the holes' (second time)"),
    ("price_mystery",    203.76, "final chorus 'and the price is the mystery' (to 206.90)"),
    ("outro_line1",      213.22, "'The survivors of a sieve' (213.22-217.44)"),
    ("outro_line2",      217.44, "'are the places where the light gets through' (to 226.88)"),
    ("last_word",        226.16, "'through' (226.16-226.88): the typed text completes; the tail plays to the hard stop"),
    ("tail",             226.88, "the last sung word ends; the clock steps on each beat from here to the last (238.47)"),
]
# the outro's sung words as typed on screen, with their transcript times (start, end); the
# transcript heard "sin" for "sieve". "are" is held, so its span is long (217.44-222.30).
OUTRO_WORDS = [
    (0, "The", 213.22, 214.64), (0, "survivors", 214.64, 215.54), (0, "of", 215.54, 216.62),
    (0, "a", 216.62, 216.94), (0, "sieve", 216.94, 217.44),
    (1, "are", 217.44, 222.30), (1, "the", 222.30, 223.70), (1, "places", 223.70, 224.24),
    (1, "where", 224.24, 224.74), (1, "the", 224.74, 225.02), (1, "light", 225.02, 225.36),
    (1, "gets", 225.36, 226.16), (1, "through.", 226.16, 226.88),
]
MUSIC_END_RAW = 238.47            # last tracked beat before the hard stop (-14 -> -76 dBFS in 0.5 s)
HARD_STOP_DB = -40.0              # the hard stop: the first frame after the last beat under this

def build():
    f = json.load(open(FEATURES))
    beats = np.array(f["beats"])
    secs = []
    for name, scene, t, why in RAW:
        snapped = t
        if t > 0:
            b = beats[np.argmin(np.abs(beats - t))]
            if abs(b - t) <= 0.5:
                snapped = float(b)
        secs.append({"name": name, "scene": scene, "start": round(snapped, 3),
                     "raw": t, "why": why})
    for i, s in enumerate(secs):
        s["end"] = secs[i + 1]["start"] if i + 1 < len(secs) else round(f["duration"], 3)
    k = int(np.argmin(np.abs(beats - MUSIC_END_RAW)))
    music_end = round(float(beats[k]), 3)
    tk = f["ticks"]
    ticks = [t for t, o in zip(tk["t"], tk["grid_offset"])
             if o <= TICK_ON_GRID and any(s["name"] in TICK_SECTIONS and s["start"] <= t < s["end"]
                                          for s in secs) and t < music_end]
    db = np.array(f["rms_raw_dbfs"])
    i0 = int(music_end * f["fps"])
    hard_stop = round((i0 + int(np.argmax(db[i0:] < HARD_STOP_DB))) / f["fps"], 3)
    json.dump({"hard_stop": hard_stop, "source": "cache/features.json", "confirmed": "transcript, checked by the author, 2026-10-28", "sections": secs,
               "cues": [{"name": n, "t": t, "why": w} for n, t, w in CUES],
               "ticks": ticks, "music_end": music_end,
               "outro_words": [{"line": l, "word": w, "start": a, "end": b} for l, w, a, b in OUTRO_WORDS]},
              open(OUT, "w"), indent=1)
    return f, secs, ticks, music_end

def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"

if __name__ == "__main__":
    f, secs, ticks, music_end = build()
    fps = f["fps"]
    rms, onset, high, low = (np.array(f[k]) for k in ("rms", "onset", "high", "low"))
    beats = np.array(f["beats"])
    bar = 4 * 60 / f["tempo"]
    print(f"tempo {f['tempo']:.2f} bpm, bar {bar:.3f} s, duration {f['duration']:.3f} s, "
          f"{len(secs)} sections\n")
    print(f"{'#':>2} {'name':13s} {'scene':9s} {'start':>8s} {'end':>8s} {'len':>6s} {'bars':>5s} "
          f"{'snap':>6s} {'beats':>5s} {'ons':>4s} {'rms':>5s} {'low':>5s} {'high':>5s}")
    for i, s in enumerate(secs):
        a, b = int(s["start"] * fps), int(s["end"] * fps)
        nb = int(((beats >= s["start"]) & (beats < s["end"])).sum())
        print(f"{i + 1:2d} {s['name']:13s} {s['scene']:9s} {mmss(s['start']):>8s} {mmss(s['end']):>8s} "
              f"{s['end'] - s['start']:5.1f}s {(s['end'] - s['start']) / bar:5.1f} "
              f"{s['start'] - s['raw']:+6.2f} {nb:5d} {int(onset[a:b].sum()):4d} "
              f"{rms[a:b].mean():5.2f} {low[a:b].mean():5.2f} {high[a:b].mean():5.2f}")
    for name in TICK_SECTIONS:
        s = next(x for x in secs if x["name"] == name)
        tt = [t for t in ticks if s["start"] <= t < s["end"]]
        if tt:
            print(f"\n{name} ticks: {len(tt)}, {mmss(tt[0])} .. {mmss(tt[-1])}")
    for c in CUES:
        print(f"cue {c[0]:14s} {mmss(c[1])}  {c[2]}")
    print(f"music ends {mmss(music_end)} (last beat); hard stop {mmss(json.load(open(OUT))['hard_stop'])}\nwrote {OUT}")
