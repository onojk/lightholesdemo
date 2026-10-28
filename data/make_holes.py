#!/usr/bin/env python3
"""make_holes.py -> data/holes.json: every number the film draws, computed and checked.

    .venv/bin/python data/make_holes.py

Deterministic: no randomness at all, so the JSON is byte-identical on every run. Each block
asserts its own checks (the abacus sums to 22, the factorizations multiply back, ...), and the
script fails rather than write a wrong number.

    line     the sieve of Eratosthenes on 1..100 (intro, pre-chorus, chorus 1): stations 2, 3,
             5, 7 strike from p^2 in steps of p; the survivors are the 25 primes
    big      the same on 1..400 in four rows of 100 (final chorus): stations 2..19
    strobe   the sieve on a 100 x 100 grid, 1..10000 (the 0:37 break): stations are the 25
             primes up to 100; each cell keeps the station that strikes it first (its smallest
             prime factor); 1,229 primes survive
    wheels   the stations wrapped into wheels: wheel p is open at every residue but 0, so the
             beam reaches the cell exactly at n coprime to every wheel; the first alignments
             for wheels 2..7 (chorus 1) and 2..19 (final chorus)
    legendre Legendre's abacus for x = 100 with the primes 2, 3, 5, 7: one bead row per subset,
             sign mu(d), count floor(100 / d); the level sums 100, -117, +45, -6, 0 -> 22, the
             22 numbers up to 100 with no factor 2, 3, 5 or 7 (1 and the primes 11..97)
    mertens  the Wander: M(n) = sum of mu(k) for k <= n, n = 1..10000, against sqrt(n)
    parity   one floor and two: 139 (prime) and 143 = 11 x 13 both survive the stations 2, 3,
             5, 7, so a sieve to 10 cannot tell them apart
    lehmer   2^93 + 1 = 3^2 x 715,827,883 x 529,510,939 x 2,903,110,321; the 19-digit cofactor,
             and gears for it: each gear (a prime modulus m) is drilled at the x for which
             x^2 - N is a square mod m (Fermat's condition, N = x^2 - y^2); the answer is
             x = (p + q) / 2. The window of candidates the film turns through is checked to
             hold exactly one alignment, the answer
    rsa129   RSA-129 and its two factors (product checked), and the message
    twinkle  TWINKLE: one LED per prime power p^k (p <= 31) up to the candidates' size,
             flashing every p^k ticks with brightness log p, so the summed light on candidate n
             is the log of n's 31-smooth part; it reaches log n exactly when n is 31-smooth
"""
import json, math, os
import numpy as np
from sympy import factorint, isprime, primerange, mobius, sqrt_mod

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "holes.json")

def sieve(n, stations):
    """Strikes of each station p (p^2, p^2 + p, ... <= n), the first station to strike each
    cell (-1 if none), and the survivors >= 2."""
    first = [-1] * (n + 1)
    strikes = []
    for k, p in enumerate(stations):
        hits = list(range(p * p, n + 1, p))
        strikes.append(hits)
        for m in hits:
            if first[m] < 0:
                first[m] = k
    surv = [m for m in range(2, n + 1) if first[m] < 0]
    return strikes, first, surv

def block_line():
    st = [2, 3, 5, 7]
    strikes, first, surv = sieve(100, st)
    assert surv == list(primerange(2, 101)) and len(surv) == 25
    return {"n": 100, "stations": st, "strikes": strikes, "first": first[1:], "survivors": surv,
            "strike_total": sum(map(len, strikes))}

def block_big():
    st = list(primerange(2, 20))
    strikes, first, surv = sieve(400, st)
    assert surv == list(primerange(2, 401)) and len(surv) == 78
    return {"n": 400, "rows": 4, "stations": st, "strikes": strikes, "first": first[1:],
            "survivors": surv, "strike_total": sum(map(len, strikes))}

def block_strobe():
    st = list(primerange(2, 101))
    strikes, first, surv = sieve(10000, st)
    assert len(st) == 25 and len(surv) == 1229 and surv == list(primerange(2, 10001))
    # cell n (1..10000) at row (n - 1) // 100, column (n - 1) % 100: station index, 25 = unstruck
    cells = [25 if f < 0 else f for f in first[1:]]
    return {"n": 10000, "side": 100, "stations": st, "strike_counts": [len(h) for h in strikes],
            "cells": cells, "survivors": len(surv)}

def block_wheels():
    out = {}
    for name, ws in (("chorus", [2, 3, 5, 7]), ("final", list(primerange(2, 20)))):
        prod = math.prod(ws)
        al = [n for n in range(1, 2000) if math.gcd(n, prod) == 1][:48]
        out[name] = {"wheels": ws, "alignments": al}
    assert out["chorus"]["alignments"][:22] == [1] + list(primerange(11, 101))
    return out

def block_legendre():
    ps, x = [2, 3, 5, 7], 100
    levels = []
    for k in range(5):
        beads = []
        for mask in range(16):
            sub = [p for i, p in enumerate(ps) if mask >> i & 1]
            if len(sub) == k:
                d = math.prod(sub)
                beads.append({"d": d, "mu": int(mobius(d)), "count": x // d})
        levels.append({"size": k, "beads": beads, "sum": sum(b["mu"] * b["count"] for b in beads)})
    sums = [l["sum"] for l in levels]
    assert sums == [100, -117, 45, -6, 0] and sum(sums) == 22
    coprime = [n for n in range(1, x + 1) if math.gcd(n, 210) == 1]
    assert len(coprime) == 22 and coprime == [1] + list(primerange(11, 101))
    # pi(100) = 22 - 1 (the number 1) + 4 (the stations themselves)
    assert len(list(primerange(2, 101))) == 22 - 1 + 4
    return {"x": x, "primes": ps, "levels": levels, "sums": sums, "total": 22, "survivors": coprime}

def block_mertens():
    n = 10000
    M, s = [], 0
    for k in range(1, n + 1):
        s += int(mobius(k)); M.append(s)
    M = np.array(M)
    r = np.sqrt(np.arange(1, n + 1))
    assert np.all(np.abs(M) <= r)            # Mertens's bound holds this far (n = 1 touches it)
    return {"n": n, "M": M.tolist(), "max": int(M.max()), "argmax": int(M.argmax()) + 1,
            "min": int(M.min()), "argmin": int(M.argmin()) + 1, "end": int(M[-1])}

def block_parity():
    a, b = 139, 143
    assert isprime(a) and factorint(b) == {11: 1, 13: 1}
    assert math.gcd(a, 210) == 1 and math.gcd(b, 210) == 1
    return {"one_floor": a, "two_floors": b, "two_factors": [11, 13], "stations": [2, 3, 5, 7]}

def block_lehmer():
    N93 = 2 ** 93 + 1
    f = factorint(N93)
    assert f == {3: 2, 715827883: 1, 529510939: 1, 2903110321: 1}, f
    C = N93 // (9 * 715827883)
    p, q = 529510939, 2903110321
    assert C == 1537228672093301419 == p * q and len(str(C)) == 19
    x0, y0 = (p + q) // 2, (q - p) // 2
    assert x0 * x0 - C == y0 * y0
    # gears: primes m (not dividing 2C), holes at x mod m with x^2 - C a square mod m
    WINDOW, OVER = 110000, 240           # candidates turned through before / past the answer
    lo, hi = x0 - WINDOW, x0 + OVER
    xs = np.arange(lo, hi + 1, dtype=np.int64)
    gears, alive = [], np.ones(len(xs), bool)
    for m in primerange(3, 200):
        if C % m == 0:
            continue
        sq = {(k * k) % m for k in range(m)}
        holes = sorted(r for r in range(m) if (r * r - C) % m in sq)
        gears.append({"m": m, "holes": holes})
        hs = np.zeros(m, bool); hs[holes] = True
        alive &= hs[xs % m]
        if alive.sum() == 1:
            break
    assert alive.sum() == 1 and xs[alive][0] == x0
    for g in gears:                       # the answer is open on every gear
        assert x0 % g["m"] in g["holes"]
    return {"N93": str(N93), "small": [3, 3, 715827883], "C": str(C), "p": p, "q": q,
            "x": x0, "y": y0, "window": WINDOW, "overshoot": OVER, "gears": gears,
            "open_fraction": float(np.prod([len(g["holes"]) / g["m"] for g in gears]))}

RSA129 = int("1143816257578888676692357799761466120102182967212423625625618429357069352457338978"
             "30597123563958705058989075147599290026879543541")
RSA_P = 3490529510847650949147849619903898133417764638493387843990820577
RSA_Q = 32769132993266709549961988190834461413177642967992942539798288533

def block_rsa():
    assert RSA_P * RSA_Q == RSA129 and len(str(RSA129)) == 129
    assert isprime(RSA_P) and isprime(RSA_Q)
    return {"N": str(RSA129), "p": str(RSA_P), "q": str(RSA_Q), "digits": [129, 64, 65],
            "message": "THE MAGIC WORDS ARE SQUEAMISH OSSIFRAGE",
            "years": [1977, 1994], "machines": 1600}

def block_twinkle():
    B, N0, TICKS = 31, 1000, 160
    n1 = N0 + TICKS - 1
    leds = []
    for p in primerange(2, B + 1):
        k, pk = 1, p
        while pk <= n1:
            leds.append({"p": p, "k": k, "pk": pk, "w": math.log(p)}); k += 1; pk *= p
    cands = []
    for n in range(N0, n1 + 1):
        lit = [i for i, L in enumerate(leds) if n % L["pk"] == 0]
        s = sum(leds[i]["w"] for i in lit)
        smooth = max(factorint(n)) <= B
        assert abs(s - math.log(n)) < 1e-9 if smooth else s < math.log(n) - 1e-9
        cands.append({"n": n, "lit": lit, "sum": s, "log": math.log(n), "smooth": smooth})
    return {"bound": B, "start": N0, "leds": leds, "candidates": cands,
            "smooth_count": sum(c["smooth"] for c in cands)}

def main():
    d = {"line": block_line(), "big": block_big(), "strobe": block_strobe(), "wheels": block_wheels(),
         "legendre": block_legendre(), "mertens": block_mertens(), "parity": block_parity(),
         "lehmer": block_lehmer(), "rsa129": block_rsa(), "twinkle": block_twinkle()}
    with open(OUT, "w") as fh:
        json.dump(d, fh, separators=(",", ":"), sort_keys=True)
        fh.write("\n")
    L, M, T = d["lehmer"], d["mertens"], d["twinkle"]
    print(f"line: {d['line']['strike_total']} strikes, {len(d['line']['survivors'])} survivors; "
          f"big: {d['big']['strike_total']} strikes, {len(d['big']['survivors'])} survivors; "
          f"strobe: {d['strobe']['survivors']} survivors")
    print(f"legendre: {d['legendre']['sums']} -> {d['legendre']['total']}")
    print(f"mertens: max {M['max']} at {M['argmax']}, min {M['min']} at {M['argmin']}, M(10000) = {M['end']}")
    print(f"lehmer: x = {L['x']}, y = {L['y']}, {len(L['gears'])} gears (m = "
          f"{', '.join(str(g['m']) for g in L['gears'])}), open fraction {L['open_fraction']:.2e}")
    print(f"twinkle: {len(T['leds'])} LEDs, {T['smooth_count']} of {len(T['candidates'])} candidates smooth")
    print(f"wheels: chorus {d['wheels']['chorus']['alignments'][:8]}..., final {d['wheels']['final']['alignments'][:8]}...")
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")

if __name__ == "__main__":
    main()
