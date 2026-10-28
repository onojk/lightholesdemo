# Light Through the Holes — a demoscene music video

A demoscene music video for **"Light Through the Holes"**, a hard electronic synth-rock song:
vocoder robot boy-band lead, barbershop harmonies, measured at 94.8 bpm. It is rendered
offline and deterministically from GLSL shaders, driven by an analysis of the song.

The song tells the story of the book *Light Through the Holes: Sieves, Strikes, and the Price
of Seeing Primes* by Jonathan Kendall: Eratosthenes' stations, Legendre's ledger and the
Wander, Selberg's parity wall, the Lehmers' photoelectric sieve, RSA-129, Shamir's TWINKLE,
and the author's own lamps. Its governing image is the book's: **light only appears where
every layer is open at once**, and the darkness is built first. The palette is the cover's
(the artwork *Nihil Opera*): glowing teal and green against deep navy.

Every number on screen is real and computed: see "Where each number comes from" below.

## The song is not included

This repo has no audio in it, and the song belongs to its author. Bring your own WAV of the
song as `audio/light_holes.wav` (`audio/` is git-ignored).

## What the film shows

| section | time | scene |
|---|---|---|
| intro | 0:00 | The number line 1..100 ticks in, a decade per half beat. |
| pre-chorus | 0:05 | Grey static on "No one asked the survivors"; on "known by what was missed" it clears: the struck cells are shut and the 25 survivors, the primes, glow. |
| chorus 1 | 0:15 | Every hole opens again. On "the stations walk the line" stations 2, 3, 5, 7 stride from p², striking. On "every gear in its own time" each station's period curls into a ring and becomes a wheel, open at every residue but 0. From "wait until they all align" the wheels land on one alignment per beat (11, 13, 17, ... 97); the beam reaches the photocell, and that cell of the line lights. |
| break | 0:37 | The sieve at high speed on 1..10,000: each onset brings the next of the 25 stations down on a 100 × 100 grid; 1,229 survivors glow. |
| verse 2 | 0:46 | Legendre's abacus for x = 100 (beads 100, −117, +45, −6, 0 → 22). The Wander, the real Mertens walk to 10,000, with its ±√n envelope; on "Selberg found the wall" a grey wall rises at its end. On "one floor from two": 139 and 143 = 11 × 13 behind the same grey. |
| verse 3 | 1:17 | The photoelectric sieve, 1933: twenty gears for the 19-digit part of 2⁹³ + 1, a lamp, a mirror and a cell. The machine turns at about 5,000 candidates a second; on "the light came shining through" every hole lines up and the cell flashes; it coasts past, and on "wound it back by hand" turns back to the answer. Then x, y and the factors. |
| verse 4 | 1:46 | RSA-129's 129 digits; 1,600 machines; 1977 → 1994; "THE MAGIC WORDS ARE SQUEAMISH OSSIFRAGE" typed on the sung words; the number splits into its factors. Then TWINKLE: one LED per prime power, flashing every p^k ticks with brightness log p; the meter flares at the smooth candidates. |
| bridge | 2:32 | The theta tower from [tentimesdemo](https://github.com/onojk/tentimesdemo) assembles ring by ring; a split-flap counter 3.4 → 1.4. |
| "Ten times" | 2:52 | The key rises and the camera lifts. The long arm (stage 2 to 100·B1) against the short arm (10·B1): +42.8% against −6.4%. On "the center stays dark" the spine brightens, still grey. |
| final chorus | 3:04 | Everything lit at once: the sieve again on 1..400 with eight wheels (2..19), TWINKLE's LEDs, and the tower turning in the middle; bloom rides the choir swell; the center stays grey. |
| outro | 3:33 | "The survivors of a sieve / are the places where the light gets through." typed on the sung words, held through the tail; a clock steps on each beat of the tail and stops on the last (3:58.47). |

The theta tower keeps tentimesdemo's conventions: radius ½ − θ with θ = log p / log N; each
point coloured by the first lamp that finds it (trial division orange, rho blue, p−1 stage 1
deep green, stage 2 light green, grey for the numbers left to the quadratic sieve); the grey
spine is the wall.

## Where each number comes from

`data/make_holes.py` → `data/holes.json`. No randomness; byte-identical on every run; each
block asserts its own checks and the script fails rather than write a wrong number.

| on screen | figure | source |
|---|---|---|
| the line, the 25 survivors | the sieve of Eratosthenes on 1..100, stations 2, 3, 5, 7 from p² (104 strikes); survivors = the primes to 100 | `holes.json` `line`, checked against sympy |
| the wheels' alignments 11, 13, ..., 97 | n ≤ 100 coprime to 2·3·5·7: wheel p is open at every residue but 0, so light passes exactly there | `holes.json` `wheels.chorus` |
| 1,229; the 25 stations | the sieve on 1..10,000 with the primes to 100; each cell's first striker is its smallest prime factor | `holes.json` `strobe` |
| 100, −117, +45, −6, 0 → 22 | Legendre's sum for x = 100, primes 2, 3, 5, 7: one row per subset size, sign μ(d), ⌊100/d⌋ beads per d; the 22 = 1 and the primes 11..97 (π(100) = 22 − 1 + 4) | `holes.json` `legendre`; the book, ch. 4 |
| the Wander, ±√n, M(10,000) = −23 | M(n) = Σ μ(k) for n to 10,000 (max 35 at 8,511, min −43 at 9,861); \|M(n)\| ≤ √n holds throughout | `holes.json` `mertens` |
| 139 and 143 = 11 × 13 | a prime and a two-prime product, both coprime to 210: a sieve to 10 cannot tell one floor from two | `holes.json` `parity`; the book, ch. 7 |
| 1933, A Century of Progress, about 5,000 a second | the machine's exhibition and speed | the book, ch. 10 |
| N = 1,537,228,672,093,301,419; 529,510,939 × 2,903,110,321 | 2⁹³ + 1 = 3² × 715,827,883 × 529,510,939 × 2,903,110,321 (sympy factorint; the product is checked) | `holes.json` `lehmer`; the book, ch. 10 |
| the gears, x = 1,716,310,630, y = 1,186,799,691 | gear m (the primes 3..73) is drilled at the x for which x² − N is a square mod m (Fermat's condition, N = x² − y²); x = (p + q)/2. The film turns through the 110,000 candidates before the answer and coasts 240 past it; within that window the answer is the only alignment of all twenty gears (checked) | `holes.json` `lehmer` |
| RSA-129 and its factors | the 129-digit modulus = 3490…0577 (64 digits) × 3276…8533 (65 digits), both prime; the product is checked | `holes.json` `rsa129` |
| 1,600 machines; 1977 → 1994 | "some sixteen hundred computers"; Gardner's column, August 1977; factored April 1994 | the book, ch. 13 |
| TWINKLE's LEDs, the flares | one LED per prime power p^k ≤ 1159 with p ≤ 31 (37 LEDs), brightness log p; candidates 1000 on; the summed light is the log of a candidate's 31-smooth part, and reaches log n exactly at the smooth ones (1000, 1001, 1008, ...; checked) | `holes.json` `twinkle` |
| the tower | 4,500 real products of two primes at 72, 84 and 96 bits | `data/tower.json` from tentimesdemo (`data/make_tower.py`, seeded; reproduces the same bytes) |
| 3.4 → 1.4, "fitted c = 1.41" | p − 1 behaves like a random integer of size p/c: model input 3.4; fitted c = 1.41 on real primes | lumens-per-watt NOTES, "Real-prime measurement run" (via tentimesdemo) |
| +42.8% / −6.4%, 402 / 247 | stage 2 appended to the stage-1 pipeline at 72 bits: to 100·B1 it costs 42.8% more, to 10·B1 it saves 6.4%; stage-2 points lit at 100·B1 / 10·B1 | NOTES, "Real-prime split-half search"; `data/tower.json` |

## Requirements

- Python 3.10+, with ffmpeg on `PATH`
- a GPU or driver with EGL and OpenGL 3.3 (Mesa works headless)

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # numpy, moderngl, sympy (and mpmath, with sympy)
```

## Rebuild

```sh
# the data (already committed; both scripts are deterministic)
.venv/bin/python data/make_holes.py              # -> data/holes.json
.venv/bin/python data/make_tower.py              # -> data/tower.json

# analyse the song -> cache/features.json; then the section map and word cues -> cache/sections.json
.venv/bin/python analyze.py audio/light_holes.wav
.venv/bin/python sections.py

# the whole film at 1080p, song muxed in
.venv/bin/python render.py renders/light_holes_1080p.mp4 --audio audio/light_holes.wav --full

# one section as a 480p preview, or stills
.venv/bin/python render.py renders/verse3.mp4 --audio audio/light_holes.wav --section verse3 --res 480
.venv/bin/python render.py - --still 25.5 --still 99.1        # PNGs into renders/
```

The section boundaries and word cues in `sections.py` come from a transcript of the song with
word timestamps, checked against the written lyrics by the author (`lyrics.md`). Rendering is
deterministic: time is `frame / 30`, and grain comes from a fixed seed, so the same command
gives byte-identical frames.

The pipeline (offline GLSL renderer, audio analysis, ffmpeg mux) is adapted from the author's
earlier videos, [tentimesdemo](https://github.com/onojk/tentimesdemo) and
[laser-beam-demo](https://github.com/onojk/laser-beam-demo).

## License

MIT, see [LICENSE](LICENSE). This covers the code and data only. The song belongs to its
author and is not included.
