#!/usr/bin/env python3
"""Light Through the Holes — rendered offline.

    .venv/bin/python render.py out.mp4 --audio audio/light_holes.wav --start 0 --dur 7.5 [--res 480]
    .venv/bin/python render.py out.mp4 --audio audio/light_holes.wav --section verse3 --res 480
    .venv/bin/python render.py out.mp4 --audio audio/light_holes.wav --full [--res 2160 --crf 16]
    .venv/bin/python render.py - --still 3.2 --still 7.0          # stills only

Copied from tentimesdemo's render.py (itself from laser-beam-demo's): the render loop, uniform
plumbing, point pass for the theta tower, quarter-size two-pass bloom, ffmpeg rgb24 pipe and
audio mux are the same. Deterministic: time = frame / 30, never the wall clock; grain is a
hash of the pixel and frame number; every per-frame value is a function of t alone.

Changed for this film: the cover's palette (Nihil Opera: glowing teal and green on deep navy)
with the navy added in the post pass, so the darkness is built first and the light sits on it;
per-frame float data textures (the number line's cells); a text atlas; and shared GLSL for
the number line, the wheels and the beam (HEAD). Every number drawn comes from
data/holes.json, data/tower.json or the sources named in the README.
"""
import argparse, json, math, os, subprocess, sys, tempfile
import numpy as np
import moderngl
from sync import Sync, FPS

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SEED = 0x1405                    # the only source of noise; change it to re-roll the grain
TOWER = os.path.join(HERE, "data", "tower.json")
HOLES = os.path.join(HERE, "data", "holes.json")
SECTIONS_JSON = os.path.join(HERE, "cache", "sections.json")
BG = (0.004, 0.020, 0.062)       # deep navy, from the darkest tenth of the cover

# the number line (intro, pre-chorus, chorus 1, outro): 100 cells across, in P units
LINE_X0, LINE_PITCH = -1.62, 0.0324
LINE_Y = {"intro": 0.0, "prechorus": 0.0, "chorus1": -0.56, "outro": -0.72}
STRIKE_DIV = 16                  # chorus 1: one stride per 1/16 beat (64th notes)
WRAP_BEND, WRAP_MOVE = 0.55, 0.65    # s: a station's period curls into a ring, then flies to its slot
CHORUS_WHEELS = dict(y=0.20, R=0.165, xs=(-0.93, -0.31, 0.31, 0.93), lamp=-1.50, cell=1.50)
FINAL_WHEELS = dict(y=0.66, R=0.105, xs=tuple(-1.33 + 0.38 * k for k in range(8)), lamp=-1.66, cell=1.66)
BIG_X0, BIG_Y0, BIG_ROW = -1.62, -0.70, 0.062      # final chorus: 1..400 in four rows of 100
STROBE_X0, STROBE_Y0, STROBE_PITCH = -0.87, 0.87, 0.0175   # the 0:37 break: 100 x 100
FLASH_AREA = 0.10                # strobe: a station's flash is capped to this share of full-frame light
LEHMER_GAP = 0.045               # verse 3: gap between gears, P units
LEHMER_RATE_NOTE = 5000          # verse 3: "about 5,000 candidates per second" (chapter 10)
OVERSHOOT_DECEL = 0.5            # verse 3: s the machine takes to coast to a stop past the flash
TWINKLE_DIV = 2                  # verse 4: one candidate per 1/2 beat (eighth notes)
FLAP_C = (3.4, 1.41)             # bridge: c before and after the primes came back (NOTES via tentimesdemo)
FLIP_DUR = 0.09                  # bridge: one flap flip, s
ASSEMBLE_RINGS = 8               # bridge: rings per band, one per beat
# "Ten times, not a hundred": the 72-bit row of tentimesdemo's chorus. From NOTES ("Real-prime
# split-half search"): stage 2 appended to the stage-1 pipeline, plain; to 100 B1 it costs
# 42.8% more, to 10 B1 it saves 6.4%. Point counts come from tower.json.
ARMS = {"tentimes": (72, +42.8, -6.4)}
ARM_EL, ARM_DIST, ARM_SHIFT = 40.0, 3.1, -0.16
LIFT_EL = 16.0                   # degrees the camera rises over the key change's first bar
LABEL_W, LABEL_H, LABEL_SIZE = 400, 72, 46
FINALE_EL, FINALE_SPEED, FINALE_DIST = 20.0, 0.12, 6.3
WHEEL_IN = 0.6                   # final chorus: s for a formed wheel to fall into its slot
OUTRO_LINES = ["The survivors of a sieve", "are the places where the light gets through."]

ATLAS_W, ATLAS_H, ATLAS_FONT = 2400, 80, 56        # one text-atlas cell; DejaVu Sans Mono advance 0.602 em
GLYPHS = "0123456789,.−+=× "               # glyph cells: 10 ',' 11 '.' 12 minus 13 '+' 14 '=' 15 times 16 blank
G_COMMA, G_DOT, G_MINUS, G_PLUS, G_EQ, G_TIMES, G_BLANK = range(10, 17)
GLYPH_W, GLYPH_H, GLYPH_SIZE = 120, 170, 150

VERT = """
#version 330
in vec2 pos;
out vec2 uv;
void main() { uv = pos * 0.5 + 0.5; gl_Position = vec4(pos, 0.0, 1.0); }
"""

# Shared header for scene shaders: uv in [0,1], P() centred with y in [-1,1]; the palette;
# glyph and atlas text; the number line; wheels; beams.
HEAD = """
#version 330
in vec2 uv;
out vec4 frag;
uniform vec2 res;
uniform float t, ts, sdur, local;     // time; time / length / progress in this section
uniform float rms, low, mid, high;    // 0..1, loudness and the three bands
uniform float phrase, swell;          // ~4 s spectral centroid; smoothed choir swell
uniform float beat, since_beat;       // beats elapsed (float); seconds since the last beat
uniform float kick;                   // strong-onset pulse (spaced under 3 per second)
uniform float travel;                 // integral of rms-driven speed: a position, never jumps
uniform float music;                  // 1 while the music plays, 0 after the cut
uniform int seed;
// the cover's palette: Nihil Opera's blues, teals and greens; light against navy
const vec3 DEEP  = vec3(0.010, 0.160, 0.340);
const vec3 TEAL  = vec3(0.020, 0.600, 0.700);
const vec3 CYAN  = vec3(0.300, 0.850, 0.900);
const vec3 GREEN = vec3(0.180, 0.950, 0.580);
const vec3 WHITE = vec3(0.920, 0.960, 1.000);
const vec3 DARK  = vec3(0.300, 0.330, 0.360);  // unlit, struck, static, the spine: grey
// the tower's lamps (tentimesdemo's legend, kept so the tower reads the same)
const vec3 TD    = vec3(1.00, 0.45, 0.08);
const vec3 RHO   = vec3(0.20, 0.45, 1.00);
const vec3 PM1   = vec3(0.05, 0.62, 0.22);
const vec3 PM2   = vec3(0.50, 1.00, 0.55);
const float PI = 3.14159265;
vec2 P() { return (uv * res - 0.5 * res) / (0.5 * res.y); }
float px() { return 2.0 / res.y; }            // one output pixel in P units
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float rnd(float n) { return float(hash(uint(int(n)) ^ uint(seed))) / 4294967295.0; }
float glow(float d, float w) { return exp(-d * d / (w * w)) + 0.15 * w / (abs(d) + w); }
float seg(vec2 p, vec2 a, vec2 b, out float h) {
    vec2 pa = p - a, ba = b - a;
    h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-12), 0.0, 1.0);
    return length(pa - ba * h);
}
vec3 station_col(float k) {
    int i = int(mod(k, 4.0));
    return i == 0 ? CYAN : i == 1 ? GREEN : i == 2 ? TEAL * 1.3 : vec3(0.45, 0.70, 1.00);
}

// ---- glyphs (digits and a few signs, one drawtext call each) and the text atlas
uniform sampler2D glyphs;
uniform sampler2D atlas;
uniform float atlas_len[64];
uniform float atlas_rows;
const float NGLYPH = 17.0, GASP = 120.0 / 170.0, GADV = 90.0 / 170.0;
const float ACW = 2400.0, ACH = 80.0, AADV = 0.602 * 56.0;
float gcell(float c, vec2 q) {                // glyph c at q in [-1, 1]^2 over its cell
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    return texture(glyphs, vec2((c + q.x * 0.5 + 0.5) / NGLYPH, q.y * 0.5 + 0.5)).r;
}
// an integer v >= 0 (exact below 2^24), centred at c, glyph half-height h
float gnum(float v, vec2 p, vec2 c, float h) {
    float nd = v < 9.5 ? 1.0 : v < 99.5 ? 2.0 : v < 999.5 ? 3.0 : v < 9999.5 ? 4.0 : v < 99999.5 ? 5.0 : 6.0;
    float adv = 2.0 * h * GADV;
    float left = c.x - 0.5 * nd * adv;
    float k = floor((p.x - left) / adv);
    if (k < 0.0 || k >= nd || abs(p.y - c.y) > h) return 0.0;
    float d = mod(floor((v + 0.5) / pow(10.0, nd - 1.0 - k)), 10.0);
    return gcell(d, vec2((p.x - left - (k + 0.5) * adv) / (h * GASP), (p.y - c.y) / h));
}
// a string of glyph codes s[0..n-1], centred at c
float gcodes(float s[32], int n, vec2 p, vec2 c, float h) {
    float adv = 2.0 * h * GADV;
    float left = c.x - 0.5 * float(n) * adv;
    float k = floor((p.x - left) / adv);
    if (k < 0.0 || k >= float(n) || abs(p.y - c.y) > h) return 0.0;
    return gcell(s[int(k)], vec2((p.x - left - (k + 0.5) * adv) / (h * GASP), (p.y - c.y) / h));
}
// atlas string i, centred at c, h = half-height of its cell (P units); only the first
// `shown` characters (shown < 0: all of them)
float atext(float i, vec2 p, vec2 c, float h, float shown) {
    if (i < 0.0) return 0.0;
    vec2 q = (p - c) / h;
    float hx = ACW / ACH;
    if (abs(q.y) > 1.0 || abs(q.x) > hx) return 0.0;
    float tx = (q.x / hx * 0.5 + 0.5) * ACW;
    float left = 0.5 * (ACW - atlas_len[int(i)] * AADV);
    if (shown >= 0.0 && tx >= left + shown * AADV) return 0.0;
    return texture(atlas, vec2(tx / ACW, 1.0 - (i + 0.5 - 0.5 * q.y) / atlas_rows)).r;
}
// the x where character k of atlas string i starts (for cursors)
float atext_x(float i, vec2 c, float h, float k) {
    return c.x + (k - 0.5 * atlas_len[int(i)]) * 2.0 * AADV / ACH * h;   // a cell's half-height is 40 px
}

// ---- the number line: one texel per cell, (visible, closed, flash, glow)
uniform sampler2D cells;
uniform vec4 line_geo;                // x0, y of the first row, pitch, row step
uniform float line_n, line_cols, cell_aspect, backlight;
vec3 line_col(vec2 p, vec3 flash_col) {
    float pitch = line_geo.z;
    float col = floor((p.x - line_geo.x) / pitch);
    float rs = line_geo.w > 0.0 ? line_geo.w : 1.0;   // one row: any step
    float row = floor((line_geo.y + 0.5 * rs - p.y) / rs);
    if (col < 0.0 || col >= line_cols || row < 0.0) return vec3(0.0);
    float idx = row * line_cols + col;
    if (idx >= line_n) return vec3(0.0);
    vec4 s = texelFetch(cells, ivec2(int(idx), 0), 0);
    if (s.x <= 0.0) return vec3(0.0);
    vec2 cc = vec2(line_geo.x + (col + 0.5) * pitch, line_geo.y - row * line_geo.w);
    vec2 hs = vec2(0.5 * pitch, 0.5 * pitch * cell_aspect);
    vec2 q = abs(p - cc);
    float aa = px();
    float hole = smoothstep(0.0, aa, min(hs.x * 0.66 - q.x, hs.y * 0.80 - q.y));
    float plate = smoothstep(0.0, aa, min(hs.x * 0.92 - q.x, hs.y * 0.96 - q.y)) - hole;
    vec3 c = DEEP * 0.55 * plate;
    vec3 open_c = TEAL * (backlight + 1.1 * s.w) + CYAN * 0.6 * s.w * s.w;
    c += hole * mix(open_c, DARK * 0.20, s.y);
    c += (hole + 0.35 * plate) * flash_col * s.z;
    return c * s.x;
}

// ---- wheels: m holes on a ring at 0.7 R; hole k sits at the angle pi/2 + 2 pi (k - pos) / m,
// so the residue at the top (where the beam crosses) is pos. kind 0: open at every residue
// but 0 (the sieve's wheels); kind 1: drilled where the holes texture (row g) is 1.
uniform sampler2D holes;
vec4 wheel(vec2 p, vec2 C, float R, float m, float pos, float kind, float g, float blur, float lit, float a) {
    vec2 d = p - C;
    float r = length(d);
    float aa = px();
    if (r > R * 1.12 + 2.0 * aa || a <= 0.0) return vec4(0.0);
    float ang = atan(d.y, d.x);
    float kf = (ang - 0.5 * PI) / (2.0 * PI) * m + pos;
    float k = floor(kf + 0.5), off = kf - k;
    float res = mod(k, m);
    float open = kind < 0.5 ? step(0.5, res) : texelFetch(holes, ivec2(int(res + 0.5), int(g + 0.5)), 0).r;
    float nt = m < 12.0 ? m * 4.0 : m < 30.0 ? m * 2.0 : m;              // teeth
    float tooth = smoothstep(0.30, 0.18, abs(fract((ang / (2.0 * PI)) * nt + pos * nt / m) - 0.5));
    float edge = R * (1.0 + 0.07 * tooth);
    float body = smoothstep(edge + aa, edge - aa, r);
    float RH = 0.70 * R;
    float hr = min(0.15 * R, 0.40 * 2.0 * PI * RH / m);
    float dh = length(vec2(off * 2.0 * PI * RH / m, r - RH));
    float inhole = smoothstep(hr + aa, hr - aa, dh);
    // spinning too fast to see: the ring shows its open share as a uniform shade
    float ring = smoothstep(hr + aa, hr - aa, abs(r - RH));
    float hole_vis = mix(inhole * open, ring * 0.5, blur);
    float plug = mix(inhole * (1.0 - open), 0.0, blur);
    vec3 metal = DEEP * 0.75 + TEAL * 0.10 * smoothstep(0.5 * R, R, r);
    metal += CYAN * 0.35 * smoothstep(edge - 3.0 * aa, edge - aa, r) * body;   // rim light
    metal *= 0.8 + 0.2 * smoothstep(0.08 * R, 0.10 * R, r);
    vec3 c = metal * body * (1.0 - hole_vis);
    c += DARK * 0.45 * plug;
    float top = step(abs(k - floor(pos + 0.5)), 0.5) * step(0.5, 1.0 - blur);
    c += hole_vis * (CYAN * 0.9 * lit * top + TEAL * 0.04);
    c += WHITE * 0.25 * smoothstep(0.035 * R + aa, 0.035 * R - aa, r);   // axle
    float cover = body * (1.0 - hole_vis);
    return vec4(c * a, cover * a);
}
// a beam segment a -> b of intensity I
vec3 beam(vec2 p, vec2 a, vec2 b, float I, float w) {
    if (I <= 0.0) return vec3(0.0);
    float h; float d = seg(p, a, b, h);
    return (CYAN * 0.8 + WHITE * 0.4) * I * (exp(-d * d / (w * w)) + 0.25 * exp(-d * d / (16.0 * w * w)));
}
"""

FALLBACK = "void main() { frag = vec4(0.0, 0.0, 0.0, 1.0); }\n"   # a scene not written yet

# The point pass: the tower's points as gaussian sprites (as in tentimesdemo). One vertex per
# point: rah = (radius, angle, height in bits), attr = (lamp at 10 B1, lamp at 100 B1, s2 ratio
# q / B1, split half 0 / 1), key = the scene's own schedule value.
PTS_HEAD = """
#version 330
in vec3 rah;
in vec4 attr;
in float key;
out vec3 v_col;
out float v_a;
uniform mat4 view_proj;
uniform vec2 res;
uniform float point_px, cam_dist;
uniform float t, ts, sdur, local, rms, kick, beat, since_beat, swell, travel;
uniform int seed;
const vec3 TD    = vec3(1.00, 0.45, 0.08);
const vec3 RHO   = vec3(0.20, 0.45, 1.00);
const vec3 PM1   = vec3(0.05, 0.62, 0.22);
const vec3 PM2   = vec3(0.50, 1.00, 0.55);
const vec3 DARK  = vec3(0.30, 0.33, 0.36);
const vec3 WHITE = vec3(0.92, 0.96, 1.00);
const float BAND = 0.42;
vec3 world(vec3 q) { return vec3(2.0 * q.x * cos(q.y), (q.z - 84.0) / 12.0 * BAND, -2.0 * q.x * sin(q.y)); }
vec3 lamp_col(float l) {
    return l < 0.5 ? TD : l < 1.5 ? RHO : l < 2.5 ? PM1 : l < 3.5 ? PM2 : DARK;
}
void place(vec3 w, float size) {
    gl_Position = view_proj * vec4(w, 1.0);
    gl_PointSize = max(1.0, size * point_px * cam_dist / max(gl_Position.w, 0.1));
}
void hide() { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0; v_col = vec3(0.0); v_a = 0.0; }
"""

PTS_FRAG = """
#version 330
in vec3 v_col;
in float v_a;
out vec4 frag;
void main() {
    vec2 d = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(d, d);
    if (r2 > 1.0 || v_a <= 0.0) discard;
    frag = vec4(v_col * v_a * exp(-r2 * 3.0), 1.0);
}
"""

DOWN = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
void main() { frag = vec4(texture(src, uv).rgb, 1.0); }
"""

BLUR = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
uniform vec2 dir;
const float W[5] = float[5](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
void main() {
    vec3 c = texture(src, uv).rgb * W[0];
    for (int i = 1; i < 5; i++) {
        c += texture(src, uv + dir * float(i) * 1.5).rgb * W[i];
        c += texture(src, uv - dir * float(i) * 1.5).rgb * W[i];
    }
    frag = vec4(c, 1.0);
}
"""

POST = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D scene, bloom;
uniform vec2 res;
uniform vec3 bg;
uniform float kick, gain, bloom_gain;
uniform int frame, seed;
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float grain(ivec2 px) {
    uint h = hash(uint(px.x) + 7919u * uint(px.y) + 104729u * uint(frame) + uint(seed));
    return float(h) / 4294967295.0 - 0.5;
}
void main() {
    vec3 e = max(texture(scene, uv).rgb, 0.0);
    vec3 c = e + bloom_gain * texture(bloom, uv).rgb;
    c *= 1.0 + 0.25 * kick;                        // strong onsets lift the glow briefly
    vec2 v = uv - 0.5;
    c += bg * (1.0 - dot(v, v) * 1.2);             // the navy, darker toward the corners
    c = 1.0 - exp(-c * 1.15);                      // soft knee: glow never clips flat
    c *= clamp(1.0 - dot(v, v) * 0.5, 0.0, 1.0);   // mild vignette
    c += grain(ivec2(gl_FragCoord.xy)) * 0.03 * (0.10 + c);
    frag = vec4(clamp(c * gain, 0.0, 1.0), 1.0);
}
"""

def include(src):
    """Expand `#include "fx/<name>"` lines (shared scene code)."""
    out = []
    for line in src.splitlines():
        if line.startswith("#include "):
            out.append(include(open(os.path.join(HERE, "fx", line.split('"')[1])).read()))
        else:
            out.append(line)
    return "\n".join(out) + "\n"

class Renderer:
    def __init__(self, W, H, textures=None):
        self.W, self.H = W, H
        self.ctx = moderngl.create_standalone_context(backend="egl")
        self.quad = self.ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        def target(w, h):
            tx = self.ctx.texture((w, h), 4, dtype="f2")
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tx.repeat_x = tx.repeat_y = False
            return tx, self.ctx.framebuffer([tx])
        self.scene, self.scene_fbo = target(W, H)
        self.bw, self.bh = W // 4, H // 4
        self.b1, self.b1_fbo = target(self.bw, self.bh)
        self.b2, self.b2_fbo = target(self.bw, self.bh)
        self.out = self.ctx.renderbuffer((W, H), 3)
        self.out_fbo = self.ctx.framebuffer([self.out])
        self.down, self.blur, self.post = (self.program(s) for s in (DOWN, BLUR, POST))
        self.scenes, self.pts, self.tex, self.data = {}, {}, {}, {}
        for name, img in (textures or {}).items():
            self.add_texture(name, img)
        self.vbo_rah = self.vbo_attr = self.vbo_key = None
    def add_texture(self, name, img):
        """8-bit gray (top row first), or float32 (h, w, 4) data read with texelFetch."""
        if img.dtype == np.float32:
            h, w, _ = img.shape
            tx = self.ctx.texture((w, h), 4, np.ascontiguousarray(img).tobytes(), dtype="f4")
            tx.filter = (moderngl.NEAREST, moderngl.NEAREST)
        else:
            h, w = img.shape
            tx = self.ctx.texture((w, h), 1, np.ascontiguousarray(img[::-1]).tobytes())
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex[name] = tx
    def set_data(self, name, arr):
        """A per-frame float texture (h, w, 4): rewritten in place when its size holds."""
        h, w, _ = arr.shape
        tx = self.tex.get(name)
        if tx is None or tx.size != (w, h):
            if tx is not None:
                tx.release()
            self.add_texture(name, arr.astype("f4"))
        else:
            tx.write(np.ascontiguousarray(arr, "f4").tobytes())
    def program(self, frag):
        prog = self.ctx.program(vertex_shader=VERT, fragment_shader=frag)
        return prog, self.ctx.vertex_array(prog, [(self.quad, "2f", "pos")])
    def scene_prog(self, name):
        if name not in self.scenes:
            path = os.path.join(HERE, "fx", name + ".glsl")
            src = open(path).read() if os.path.exists(path) else FALLBACK
            self.scenes[name] = self.program(HEAD + include(src))
        return self.scenes[name]
    def load_points(self, rah, attr):
        self.n_pts = len(rah)
        self.vbo_rah = self.ctx.buffer(rah.tobytes())
        self.vbo_attr = self.ctx.buffer(attr.tobytes())
        self.vbo_key = self.ctx.buffer(reserve=4 * self.n_pts)
    def points_prog(self, name):
        if name not in self.pts:
            path = os.path.join(HERE, "fx", name + ".pts.glsl")
            if not os.path.exists(path) or self.vbo_rah is None:
                self.pts[name] = None
            else:
                prog = self.ctx.program(vertex_shader=PTS_HEAD + open(path).read(), fragment_shader=PTS_FRAG)
                binds = [(self.vbo_rah, "3f", "rah"), (self.vbo_attr, "4f", "attr"), (self.vbo_key, "1f", "key")]
                vao = self.ctx.vertex_array(prog, [b for b in binds if b[2] in prog])
                self.pts[name] = (prog, vao)
        return self.pts[name]
    @staticmethod
    def set(prog, uniforms):
        for k, v in uniforms.items():
            if k in prog:
                if isinstance(v, bytes):                       # a matrix, GL column-major
                    prog[k].write(v)
                elif isinstance(v, np.ndarray):
                    buf = np.zeros(prog[k].array_length * prog[k].dimension, "f4")
                    buf[:v.size] = v.ravel()[:buf.size]
                    prog[k].write(buf.tobytes())
                else:
                    prog[k].value = v
    def frame(self, name, u, frame_no, gain=1.0, bloom_gain=0.9, key=None, bg=BG):
        prog, vao = self.scene_prog(name)
        for k in [k for k in u if k.startswith("tex_")]:
            self.set_data(k[4:], u.pop(k))
        self.set(prog, dict(u, res=(self.W, self.H), seed=SEED))
        for unit, (k, tx) in enumerate(self.tex.items(), start=1):
            if k in prog:
                tx.use(unit); prog[k].value = unit
        self.scene_fbo.use(); vao.render(moderngl.TRIANGLE_STRIP)
        pts = self.points_prog(name)
        if pts:
            if key is not None:
                self.vbo_key.write(key.tobytes())
            prog, vao = pts
            self.set(prog, dict(u, res=(self.W, self.H), seed=SEED,
                                point_px=2.4 * self.H / 480, cam_dist=u.get("cam_dist", CAM_DIST)))
            self.ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            vao.render(moderngl.POINTS)
            self.ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        p, v = self.down
        self.scene.use(0); p["src"].value = 0
        self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        p, v = self.blur
        p["src"].value = 0
        for _ in range(2):
            self.b1.use(0); p["dir"].value = (1 / self.bw, 0)
            self.b2_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
            self.b2.use(0); p["dir"].value = (0, 1 / self.bh)
            self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        p, v = self.post
        self.scene.use(0); self.b1.use(1)
        p["scene"].value, p["bloom"].value = 0, 1
        self.set(p, {"res": (self.W, self.H), "kick": u.get("kick", 0.0), "gain": gain, "bg": bg,
                     "bloom_gain": bloom_gain, "frame": frame_no, "seed": SEED})
        self.out_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        return self.out_fbo.read(components=3)                 # bottom row first

def text_image(lines, size, w, h, font=FONT_MONO, spacing=0):
    """White text on black from ffmpeg's drawtext, 8-bit gray, top row first (from
    laser-beam-demo)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(lines))
    try:
        vf = (f"drawtext=fontfile={font}:textfile={fh.name}:fontsize={size}:fontcolor=white:"
              f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing={spacing}:expansion=none")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}",
                              "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(fh.name)
    return np.frombuffer(raw, np.uint8).reshape(h, w)

def glyph_atlas():
    """GLYPHS in fixed cells, cut from ONE drawtext call at their monospace slots, so every
    glyph sits on the same baseline (a comma low, a minus at mid-height); the last is blank."""
    adv = 0.602 * GLYPH_SIZE
    x0, w = GLYPH_W, int(GLYPH_W * 2 + adv * len(GLYPHS))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(GLYPHS)
    try:
        vf = (f"drawtext=fontfile={FONT_MONO}:textfile={fh.name}:fontsize={GLYPH_SIZE}:fontcolor=white:"
              f"x={x0}:y=(h-text_h)/2:expansion=none")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{GLYPH_H}",
                              "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(fh.name)
    img = np.frombuffer(raw, np.uint8).reshape(GLYPH_H, w)
    cells = []
    for k in range(len(GLYPHS)):
        c = int(round(x0 + (k + 0.5) * adv)) - GLYPH_W // 2
        cells.append(img[:, c:c + GLYPH_W] if GLYPHS[k] != " " else np.zeros((GLYPH_H, GLYPH_W), np.uint8))
    return np.hstack(cells)

class Atlas:
    """Every fixed string on screen, one per ATLAS_W x ATLAS_H cell, all at ATLAS_FONT, so a
    string's characters sit in monospace slots (typed text reveals by slot)."""
    def __init__(self):
        self.strings = []
    def __call__(self, s):
        if s not in self.strings:
            assert len(s) <= ATLAS_W / (0.602 * ATLAS_FONT), s
            self.strings.append(s)
        return float(self.strings.index(s))
    def build(self):
        assert len(self.strings) <= 64
        img = np.vstack([text_image([s], ATLAS_FONT, ATLAS_W, ATLAS_H) for s in self.strings])
        return img, np.array([len(s) for s in self.strings], "f4")

def codes(text):
    """Glyph codes for a string of digits and signs, as a 32-slot array, and its length."""
    a = np.full(32, G_BLANK, "f4")
    for i, ch in enumerate(text):
        a[i] = GLYPHS.index(ch)
    return a, len(text)

def ffmpeg_writer(path, W, H, start, dur, audio, crf, preset, song_end):
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", audio]
    cmd += ["-vf", "vflip,format=yuv420p", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv"]
    if audio:
        af = "apad"
        if start + dur >= song_end - 1e-3:
            af += f",afade=t=out:st={dur - 0.04:.6f}:d=0.04"
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += ["-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)

def save_png(buf, W, H, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "-s", f"{W}x{H}", "-i", "-", "-vf", "vflip", path], input=buf, check=True)

LAMPS = ("td", "rho", "pm1_s1", "pm1_s2", "dark")
SPINE_N = 90
CAM_DIST, FOV = 3.9, 30.0
BAND = 0.42

def perspective(fov, aspect, near=0.1, far=50.0):
    f = 1 / np.tan(np.radians(fov) / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
                     [0, 0, -1, 0]], "f4")

def look_at(eye, target, up):
    f = target - eye; f = f / np.linalg.norm(f)
    r = np.cross(f, up); r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4, dtype="f4")
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m

def orbit(azimuth, elevation, aspect, dist=CAM_DIST, target=(0.0, 0.0, 0.0), shift=0.0, shift_y=0.0, inverse=False):
    """view-projection for a camera circling the tower's axis, as GL column-major bytes (with
    inverse=True, also its inverse); shift / shift_y move the picture in NDC."""
    el = np.radians(min(elevation, 89.9))
    tgt = np.array(target, "f4")
    eye = tgt + dist * np.array([np.cos(el) * np.sin(azimuth), np.sin(el), np.cos(el) * np.cos(azimuth)], "f4")
    up = np.array([-np.sin(azimuth), 0.0, -np.cos(azimuth)], "f4") if elevation >= 89.9 else np.array([0, 1, 0], "f4")
    sh = np.eye(4, dtype="f4"); sh[0, 3] = shift; sh[1, 3] = shift_y
    vp = (sh @ perspective(FOV, aspect) @ look_at(eye, tgt, up)).astype("f8")
    b = vp.T.astype("f4").tobytes()
    return (b, np.linalg.inv(vp).T.astype("f4").tobytes()) if inverse else b

def tower_arrays(tower):
    rah, attr = [], []
    for s in tower["sizes"]:
        P = s["points"]
        for i in range(len(P["p"])):
            r2 = P["s2_ratio"][i]
            rah.append((P["radius"][i], P["angle"][i], s["n"]))
            attr.append((LAMPS.index(P["lamp"][i]), LAMPS.index(P["lamp_100"][i]),
                         -1.0 if r2 is None else r2, 0.0 if P["half"][i] == "A" else 1.0))
    for k in range(SPINE_N):
        rah.append((0.0, 0.0, 66.0 + 36.0 * k / (SPINE_N - 1)))
        attr.append((5, 5, -1.0, 0.0))
    return np.array(rah, "f4"), np.array(attr, "f4")

def ease(x):
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3 - 2 * x)

def ease_out(x):
    x = float(np.clip(x, 0.0, 1.0))
    return 1 - (1 - x) ** 3

def comma(n):
    return f"{n:,}"

class SieveShow:
    """The sieve as a show, as a function of t: a number line of n cells; stations p that stride
    from p^2 in steps of p, striking (flash, then the cell closes); each station's period then
    curls into a ring and becomes a wheel (open at every residue but 0) that flies to its slot;
    the wheels turn, landing on one alignment per beat, where the beam reaches the cell and the
    line's cell for that candidate lights. Everything here is read off data/holes.json."""
    def __init__(self, sync, line, wheels_al, geo, slots, t_strike, t_strike_end, strike_dt,
                 t_wrap, wrap_gap, t_align, downbeat0, wheels_in=None):
        """wheels_in: if set, the wheels arrive already formed at that time (falling into
        their slots over WHEEL_IN s) instead of curling out of the stations' periods."""
        self.sync, self.n, self.geo, self.slots = sync, line["n"], geo, slots
        self.wheels_in = wheels_in
        self.stations = line["stations"]
        beat = 60 / sync.tempo
        # strike times: (cell index 0-based, time, station k)
        self.strikes = []
        self.finish = []
        for k, (p, hits) in enumerate(zip(self.stations, line["strikes"])):
            dt = strike_dt if strike_dt else (t_strike_end - t_strike) / max(1, len(hits) - 1)
            ts = [t_strike + j * dt for j in range(len(hits))]
            self.strikes += [(m - 1, x, k) for m, x in zip(hits, ts)]
            self.finish.append(ts[-1] if ts else t_strike)
        self.s_cell = np.array([s[0] for s in self.strikes]); self.s_t = np.array([s[1] for s in self.strikes])
        self.s_k = np.array([s[2] for s in self.strikes])
        self.first_t = np.full(self.n, np.inf)
        for c, x in zip(self.s_cell, self.s_t):
            self.first_t[c] = min(self.first_t[c], x)
        # wraps: in the order the stations finish (the shortest walks first), one per wrap_gap
        order = sorted(range(len(self.stations)), key=lambda k: (self.finish[k], -self.stations[k]))
        self.wrap_t = np.zeros(len(self.stations))
        for j, k in enumerate(order):
            self.wrap_t[k] = max(t_wrap + j * wrap_gap, self.finish[k] + 0.1)
        # alignments, one per beat from t_align
        self.al = wheels_al
        bt = sync.beat_t
        self.land = bt[bt >= t_align][:len(self.al)]
        self.t_align = t_align
        i0 = int(np.argmin(np.abs(bt - downbeat0)))
        self.downbeats = set(np.round(bt[i0::4], 4))
        self.beat = beat

    def candidate(self, t):
        """The candidate at the beam as a float (the wheels' rotation), and the index of the
        last alignment landed (-1 before the first)."""
        L, al = self.land, self.al
        if t < L[0]:
            return float(al[0]), -1
        j = int(np.searchsorted(L, t, side="right")) - 1
        if j >= len(L) - 1:
            return float(al[len(L) - 1]), len(L) - 1
        a, b = L[j], L[j + 1]
        x = (t - a - 0.35 * (b - a)) / (0.65 * (b - a))       # rest 35% of the beat, then turn
        return al[j] + (al[j + 1] - al[j]) * ease_out(x) ** 1.0, j

    def state(self, t, cells_vis, x_strip_y):
        """Uniforms for frame time t. cells_vis: per-cell visibility (from the scene)."""
        n = self.n
        C = np.zeros((1, n, 4), "f4")
        C[0, :, 0] = cells_vis
        C[0, :, 1] = (t >= self.first_t).astype("f4")
        age = t - self.s_t
        m = (age >= 0) & (age < 0.8)
        fl = np.zeros(n); np.add.at(fl, self.s_cell[m], np.exp(-age[m] / 0.09))
        C[0, :, 2] = np.minimum(fl, 1.6)
        g = self.geo                                           # x0, y0, pitch, row step, cols
        cols = g[4]
        cell_xy = lambda i: (g[0] + ((i % cols) + 0.5) * g[2], g[1] - (i // cols) * g[3])
        # stations: the striding marker, until its walk ends
        sta = np.zeros((8, 4), "f4"); nsta = 0
        for k, p in enumerate(self.stations):
            ts = self.s_t[self.s_k == k]; cs = self.s_cell[self.s_k == k]
            if len(ts) == 0 or t < ts[0] - 0.15 or t > self.finish[k] + 0.25:
                continue
            j = int(np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 1))
            a = float(np.clip((t - ts[0] + 0.15) / 0.15, 0, 1) * np.clip((self.finish[k] + 0.25 - t) / 0.2, 0, 1))
            sta[nsta] = (cs[j], a, p, k); nsta += 1
        # strips and wheels
        strip = np.zeros((8, 4), "f4"); strip2 = np.zeros((8, 4), "f4"); nstrip = 0
        whl = np.zeros((8, 4), "f4"); whl2 = np.zeros((8, 4), "f4")
        cand, jl = self.candidate(t)
        rn = int(round(cand)); dfr = abs(cand - rn)
        opens = []
        for k, p in enumerate(self.stations):
            t0 = self.wrap_t[k]
            # the period's strip rises from the station's last stride ...
            last = int(self.s_cell[self.s_k == k][-1]) if (self.s_k == k).any() else p - 1
            sx, sy = cell_xy(last)
            ax = sx - 0.5 * g[2] * (p - 1)
            A0 = np.array([ax, x_strip_y]); scale0 = 1.0
            xb = (t - t0) / WRAP_BEND
            sx_, sy_, R_, Rf = self.slots["xs"][k], self.slots["y"], self.slots["R"], None
            ring0 = p * g[2] * scale0 / (2 * np.pi)
            if self.wheels_in is not None:
                x = (t - self.wheels_in) / WHEEL_IN
                if x >= 0:
                    e = ease(x)
                    whl[k] = (sx_, sy_ + 0.45 * (1 - e) ** 2, R_, float(np.clip(x * 3, 0, 1)))
                    whl2[k] = (p, cand % p, 0.0, 0.0)
                xb = xm = -1.0
            if 0 <= xb < 1.0:
                w = ease(xb)
                strip[nstrip] = (max(w, 0.02), A0[0], A0[1] + 0.06 * ease(xb * 2), scale0)
                strip2[nstrip] = (p, float(np.clip(xb * 4, 0, 1)), 0, 0); nstrip += 1
            if self.wheels_in is None:
                xm = (t - t0 - WRAP_BEND) / WRAP_MOVE
            if xm >= 0:
                e = ease(xm)
                c0 = np.array([A0[0], A0[1] + 0.06 - ring0])
                c1 = np.array([sx_, sy_])
                c = c0 + (c1 - c0) * e
                R = (ring0 / 0.70) + (R_ - ring0 / 0.70) * e
                # handed over from the ring with its struck cell where the ring had it; once in
                # its slot, the wheel turns (0.8 s) to the candidate and then follows it
                pos0 = p / 2 - 0.5
                pos = pos0 + (cand - pos0) * ease((t - t0 - WRAP_BEND - WRAP_MOVE) / 0.8)
                whl[k] = (c[0], c[1], R, float(np.clip(xm * 6, 0, 1)))
                whl2[k] = (p, pos % p, 0.0, 0.0)
            o = float((rn % p) != 0) * np.exp(-(dfr / 0.12) ** 2) if t >= self.land[0] - 0.5 else 0.0
            opens.append(o)
        # the beam: lamp -> wheels (by slot, left to right) -> cell; lit from the first landing
        lamp_on = float(np.clip((t - (self.land[0] - 1.2)) / 0.6, 0, 1))
        if self.wheels_in is not None:
            lamp_on = float(np.clip((t - self.wheels_in) / WHEEL_IN, 0, 1))
        I = [lamp_on]
        for k in range(len(self.stations)):
            I.append(I[-1] * opens[k])
        for k in range(len(self.stations)):
            whl2[k][3] = I[k + 1]                             # light in this wheel's top hole
        flash = 0.0
        if jl >= 0:
            lt = self.land[jl]
            down = round(float(lt), 4) in self.downbeats
            flash = float(np.exp(-(t - lt) / 0.14)) * (1.0 if down else 0.6)
        # the line's cell for every candidate the beam has reached glows
        for j in range(jl + 1):
            c = self.al[j] - 1
            if 0 <= c < n:
                C[0, c, 3] = max(C[0, c, 3], 0.55 + 0.9 * float(np.exp(-(t - self.land[j]) / 0.3)))
        return C, {"sta": sta, "n_sta": nsta, "strip": strip, "strip2": strip2, "n_strip": nstrip,
                   "whl": whl, "whl2": whl2, "n_whl": len(self.stations),
                   "beam_I": np.array(I, "f4"), "lamp_on": lamp_on, "land_flash": flash,
                   "cand": float(self.al[max(jl, 0)]), "cand_a": float(jl >= 0),
                   "beam_y": self.slots["y"] + 0.70 * self.slots["R"],
                   "lamp_x": self.slots["lamp"], "cell_x": self.slots["cell"]}

class Film:
    def __init__(self, W, H, scene=None):
        self.sync = Sync()
        self.scene = scene
        self.aspect = W / H
        self.H = json.load(open(HOLES))
        tower = json.load(open(TOWER))
        A = self.atlas = Atlas()
        self.texts_init(A)
        img, lens = A.build()
        labels = self.arm_labels(tower)
        L = self.H["lehmer"]
        hole_tex = np.zeros((len(L["gears"]), 80, 4), "f4")
        for g, gear in enumerate(L["gears"]):
            hole_tex[g, gear["holes"], 0] = 1.0
        self.r = Renderer(W, H, {"glyphs": glyph_atlas(), "atlas": img, "labels": labels, "holes": hole_tex,
                                 "walk_tex": self.walk_texture()})
        self.atlas_u = {"atlas_len": lens, "atlas_rows": float(len(lens))}
        self.rah, self.attr = tower_arrays(tower)
        self.r.load_points(self.rah, self.attr)
        self.keys = {}
        self.flap_init()
        self.shows = {}
        print(f"atlas: {len(lens)} strings; lehmer: {len(L['gears'])} gears; tower {len(self.rah)} sprites",
              file=sys.stderr)

    # ---------------------------------------------------------------- shared text
    def texts_init(self, A):
        H = self.H
        L, R = H["lehmer"], H["rsa129"]
        self.T = {
            "decades": [A(str(k)) for k in (1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)],
            "survivors25": A("25 survivors: the primes to 100"),
            "strobe_count": A(f"{comma(H['strobe']['survivors'])} survivors: the primes to {comma(H['strobe']['n'])}"),
            "strobe_title": A("stations: the 25 primes to 100"),
            "leg_title": A("Legendre: x = 100, stations 2, 3, 5, 7"),
            "leg_rows": [A(s) for s in ("+100", "−117", "+45", "−6", "0")],
            "leg_total": A("100 − 117 + 45 − 6 + 0 = 22"),
            "leg_list": A(" ".join(str(x) for x in H["legendre"]["survivors"][:12])),
            "leg_list2": A(" ".join(str(x) for x in H["legendre"]["survivors"][12:])),
            "walk_title": A("the Wander: M(n) = μ(1) + μ(2) + ... + μ(n), n to 10,000"),
            "walk_env": A("±√n"),
            "walk_end": A(f"M(10,000) = {H['mertens']['end']}".replace("-", "−")),
            "wall": A("Selberg: the parity wall"),
            "t139": A("139"), "t143": A("143 = 11 × 13"),
            "floors": A("one floor          two floors"),
            "par_note": A("both survive 2, 3, 5, 7: the sieve sees the same stone"),
            "fair": A("1933 · A Century of Progress · Chicago"),
            "fair2": A(f"{len(L['gears'])} gears, each drilled where x² − N is a square"),
            "N19": A(f"N = {comma(int(L['C']))}"),
            "x_eq": A("x ="),
            "res_xy": A(f"x = {comma(L['x'])}   y = {comma(L['y'])}"),
            "res_pq": A(f"x − y = {comma(L['p'])}   x + y = {comma(L['q'])}"),
            "res_93": A(f"2⁹³ + 1 = 3² × 715,827,883 × {comma(L['p'])} × {comma(L['q'])}"),
            "rsa_lines": [A(R["N"][i:i + 43]) for i in range(0, 129, 43)],
            "rsa_title": A("RSA-129 · 1977 · 129 digits"),
            "rsa_machines": A(f"{comma(R['machines'])} machines"),
            "rsa_years": A(f"{R['years'][0]} → {R['years'][1]}: seventeen years"),
            "msg1": A("THE MAGIC WORDS ARE"), "msg2": A("SQUEAMISH OSSIFRAGE"),
            "rsa_p": A(R["p"]), "rsa_q": A("× " + R["q"]),
            "tw_title": A(f"TWINKLE: one LED per prime power, p ≤ {H['twinkle']['bound']}; brightness log p"),
            "tw_smooth": A(f"smooth: the light adds up to log n"),
            "flap_cap": A("fitted c = 1.41"),
            "outro": [A(s) for s in OUTRO_LINES],
        }

    def arm_labels(self, tower):
        cells = []
        for name, (n, plong, pshort) in ARMS.items():
            P = next(x for x in tower["sizes"] if x["n"] == n)["points"]
            cl, cs = P["lamp_100"].count("pm1_s2"), P["lamp"].count("pm1_s2")
            self.arm_counts = (cl, cs)
            print(f"{name}: {n}-bit, stage-2 points lit {cl} (100x) / {cs} (10x), "
                  f"cost {plong:+.1f}% / {pshort:+.1f}%", file=sys.stderr)
            for txt in (f"{plong:+.1f}%", f"{pshort:+.1f}%".replace("-", "−"), f"{cl}", f"{cs}",
                        "100× B1", "10× B1", f"{n}-bit", "qs"):
                cells.append(text_image([txt], LABEL_SIZE, LABEL_W, LABEL_H))
        cells += [np.zeros((LABEL_H, LABEL_W), np.uint8)] * (16 - len(cells))
        return np.vstack(cells)

    def walk_texture(self):
        """The Wander as 1,600 columns: per column, the min and max of M(n) over its n, and
        sqrt(n) at its right edge (texelFetch, exact)."""
        M = np.array(self.H["mertens"]["M"], float)
        cols = 1600
        T = np.zeros((1, cols, 4), "f4")
        for i in range(cols):
            a, b = i * len(M) // cols, (i + 1) * len(M) // cols
            T[0, i] = (M[a:b].min(), M[a:b].max(), np.sqrt(b), M[b - 1])
        return T

    def key(self, s):
        if s["name"] not in self.keys:
            fn = getattr(self, "key_" + s["scene"], None)
            self.keys[s["name"]] = None if fn is None else fn(s).astype("f4")
        return self.keys[s["name"]]

    # ---------------------------------------------------------------- intro, pre-chorus, chorus 1
    def line_show(self):
        if "chorus" not in self.shows:
            c, b = self.sync.cues, 60 / self.sync.tempo
            s = self.sync.by_name["chorus1"]
            geo = (LINE_X0, LINE_Y["chorus1"], LINE_PITCH, 0.0, 100)
            self.shows["chorus"] = SieveShow(self.sync, self.H["line"], self.H["wheels"]["chorus"]["alignments"], geo,
                                             CHORUS_WHEELS, c["stations"], None, b / STRIKE_DIV,
                                             c["every_gear"], b / 2, c["align"], s["start"])
        return self.shows["chorus"]

    def intro_visible(self, t):
        """The line ticks in, a decade per half beat over the last ten half beats before the
        voice, each decade's ten cells evenly through its half beat."""
        bt = self.sync.beat_t
        half = np.sort(np.r_[bt, 0.5 * (bt[1:] + bt[:-1])])
        t_pre = self.sync.by_name["prechorus"]["start"]
        h = half[half < t_pre - 1e-3][-10:]
        step = 60 / self.sync.tempo / 2 / 10                   # a decade's ten cells fill its half beat
        t_on = np.array([h[k // 10] + (k % 10) * step for k in range(100)])
        return np.clip((t - t_on) / 0.05, 0, 1), t_on

    def uniforms_sieve(self, s, u):
        t, c = u["t"], self.sync.cues
        name = s["name"]
        out = {"line_n": 100.0, "line_cols": 100.0, "cell_aspect": 1.7, "decades": np.array(self.T["decades"], "f4")}
        vis, t_on = self.intro_visible(t)
        static_a, glow_pr, lab_a, y = 0.0, 0.0, 1.0, LINE_Y["intro"]
        backlight = 0.10
        tick = 0.0
        if name == "intro":
            j = np.nonzero(t >= t_on)[0]
            tick = float(np.exp(-(t - t_on[j[-1]]) / 0.06)) if len(j) else 0.0
            lab_a = float(np.clip((t - t_on[9]) / 0.3, 0, 1))
            C = np.zeros((1, 100, 4), "f4"); C[0, :, 0] = vis
            C[0, :, 2] = np.where((t - t_on >= 0) & (t - t_on < 0.5), 0.5 * np.exp(-np.maximum(t - t_on, 0) / 0.08), 0)
            out.update({"tex_cells": C})
        elif name == "prechorus":
            on, mid_, off = s["start"], c["survivors"], c["known"]
            static_a = float(np.clip((t - on) / (mid_ - on), 0, 1) * np.clip((off - t) / 0.08, 0, 1))
            glow_pr = float(np.clip((t - off) / 0.25, 0, 1))
            C = np.zeros((1, 100, 4), "f4"); C[0, :, 0] = 1.0
            surv = np.array(self.H["line"]["survivors"]) - 1
            if t >= off:
                C[0, :, 1] = 1.0; C[0, surv, 1] = 0.0
                C[0, surv, 3] = glow_pr * (0.6 + 0.25 * np.exp(-(t - off) / 0.6))
            out.update({"tex_cells": C})
            backlight = 0.10 * (1 - glow_pr)
        else:                                                   # chorus 1
            show = self.line_show()
            x = ease((t - s["start"]) / 1.4)
            y = LINE_Y["intro"] + (LINE_Y["chorus1"] - LINE_Y["intro"]) * x
            C, w = show.state(t, np.ones(100), LINE_Y["chorus1"] + 0.11)
            # the pre-chorus's survivors fade as every hole opens again
            surv = np.array(self.H["line"]["survivors"]) - 1
            C[0, surv, 3] = np.maximum(C[0, surv, 3], 0.6 * float(np.clip(1 - (t - s["start"]) / 0.6, 0, 1)))
            backlight = 0.10 + 0.22 * float(np.clip((t - s["start"]) / 0.5, 0, 1)) * (0.75 + 0.25 * np.exp(-u["since_beat"] / 0.2))
            out.update(w); out["tex_cells"] = C
        out.update({"line_geo": (LINE_X0, y, LINE_PITCH, 0.0), "static_a": static_a, "glow_pr": glow_pr,
                    "lab_a": lab_a, "backlight": backlight, "tick": tick,
                    "surv_a": glow_pr if name == "prechorus" else 0.0, "t_surv": self.T["survivors25"],
                    "chorus": float(name == "chorus1")})
        return out

    # ---------------------------------------------------------------- the 0:37 break: the strobe
    def uniforms_strobe(self, s, u):
        """The sieve at high speed on 1..10,000: each detected onset of the break (at least
        0.2 s apart) brings the next station down on the whole grid at once, until all 25 have
        struck; the cells a station strikes first flash and close. A station's flash is scaled
        so its lit area never exceeds FLASH_AREA of the frame (station 2 strikes half the
        grid). Then the 1,229 survivors glow."""
        S = self.H["strobe"]
        if not hasattr(self, "_strobe"):
            on = [x for x in self.sync.onset_t if s["start"] <= x < s["end"]]
            steps, last = [], -1e9
            for x in on:
                if x - last >= 0.2:
                    steps.append(x); last = x
            b16 = 60 / self.sync.tempo / 4
            while len(steps) < len(S["stations"]):
                steps.append(steps[-1] + b16)
            self._strobe = (np.array(steps[:len(S["stations"])]), np.array(S["cells"]))
            print(f"strobe: 25 stations on onsets {self._strobe[0][0]:.2f}..{self._strobe[0][-1]:.2f} s", file=sys.stderr)
        steps, cells = self._strobe
        t = u["t"]
        k = int(np.searchsorted(steps, t, side="right")) - 1
        C = np.zeros((1, 10000, 4), "f4")
        C[0, :, 0] = 1.0
        struck = cells < 25
        C[0, :, 1] = struck & (cells <= k)
        if k >= 0:
            m = cells == k
            frac = m.mean()
            C[0, m, 2] = min(1.4, FLASH_AREA / max(frac, 1e-9) * 0.35) * np.exp(-(t - steps[k]) / 0.10)
        done = float(np.clip((t - steps[-1] - 0.25) / 0.5, 0, 1))
        C[0, ~struck, 3] = 0.25 + 0.5 * done
        C[0, 0, 3] = 0.0                                       # 1 is not a survivor of Eratosthenes
        C[0, 0, 1] = 1.0
        return {"tex_cells": C, "line_geo": (STROBE_X0 * 1.0, STROBE_Y0, STROBE_PITCH, STROBE_PITCH),
                "line_n": 10000.0, "line_cols": 100.0, "cell_aspect": 1.0,
                "backlight": 0.12 + 0.25 * u["high"], "p_now": float(S["stations"][max(k, 0)]),
                "p_a": float(k >= 0) * (1 - done), "k_now": float(k), "done": done,
                "t_count": self.T["strobe_count"], "t_title": self.T["strobe_title"]}

    # ---------------------------------------------------------------- verse 2: Legendre, the Wander, Selberg
    def uniforms_legendre(self, s, u):
        t, c = u["t"], self.sync.cues
        Lg = self.H["legendre"]
        times = [s["start"] + 0.2, c["abacus"] - 2.44, c["abacus"] - 0.84, c["abacus"] + 0.94, c["abacus"] + 1.92]
        # rows: "+100" with the section; "took away" (48.58), "put back" (50.18), "minus" (51.96), "abacus" (52.94)
        row_a = np.array([np.clip((t - x) / 0.35, 0, 1) for x in times], "f4")
        grp = np.zeros((5, 8), "f4"); gd = np.zeros((5, 8), "f4"); ng = np.zeros(5, "f4")
        for i, lv in enumerate(Lg["levels"]):
            for j, b in enumerate(lv["beads"]):
                grp[i, j], gd[i, j] = b["count"], b["d"]
            ng[i] = len(lv["beads"])
        total = float(np.clip((t - c["abacus"] - 2.88) / 0.4, 0, 1))      # "keep the count on track" 53.90
        fade_ab = float(np.clip((t - c["wander"]) / 0.6, 0, 1))
        walk = float(np.clip((t - c["wander"]) / (c["stray"] + 4.4 - c["wander"]), 0, 1))
        env = float(np.clip((t - c["stray"]) / 1.5, 0, 1))
        wall = ease((t - c["selberg_wall"]) / 0.7)
        towers = float(np.clip((t - c["one_floor"] + 1.2) / 0.6, 0, 1))
        par = float(np.clip((t - c["one_floor"]) / 0.4, 0, 1))
        return {"row_a": row_a, "grp": grp, "gd": gd, "ng": ng, "total": total, "fade_ab": fade_ab,
                "walk_on": float(t >= c["wander"] - 0.2), "walk": walk, "env": env, "wall": wall,
                "towers": towers, "par": par,
                "t_rows": np.array(self.T["leg_rows"], "f4"), "t_total": self.T["leg_total"],
                "t_title": self.T["leg_title"], "t_list": self.T["leg_list"], "t_list2": self.T["leg_list2"],
                "t_walk": self.T["walk_title"], "t_env": self.T["walk_env"], "t_end": self.T["walk_end"],
                "t_wall": self.T["wall"], "t139": self.T["t139"], "t143": self.T["t143"],
                "t_floors": self.T["floors"], "t_par": self.T["par_note"]}

    # ---------------------------------------------------------------- verse 3: the photoelectric sieve
    def lehmer_layout(self):
        if not hasattr(self, "_lay"):
            G = self.H["lehmer"]["gears"]
            rows = [G[:10], G[10:20]]
            lay, beams = [], []
            ys = (0.30, -0.22)
            for ri, row in enumerate(rows):
                Rs = [0.050 + 0.0013 * g["m"] for g in row]
                width = sum(2 * r for r in Rs) + LEHMER_GAP * (len(Rs) - 1)
                x = -0.5 * width
                for g, r in zip(row, Rs):
                    lay.append((x + r, ys[ri] - 0.70 * r, r, g["m"]))
                    x += 2 * r + LEHMER_GAP
            self._lay = (lay, ys)
        return self._lay

    def lehmer_x(self, t):
        """The candidate x at time t (an exact integer, plus a fraction for the turn), and the
        machine's state: turning at a steady rate through WINDOW candidates to the answer on
        "the light came shining through"; coasting OVERSHOOT candidates past it; still; wound
        back by hand from "wound it back" to land on the answer just before "read what it had
        found"."""
        L, c, s = self.H["lehmer"], self.sync.cues, self.sync.by_name["verse3"]
        x0, W, O = L["x"], L["window"], L["overshoot"]
        t0, t1 = s["start"], c["shining"]
        rate = W / (t1 - t0)
        if t < t1:
            d = -(t1 - t) * rate
        elif t < t1 + OVERSHOOT_DECEL:
            y = (t - t1) / OVERSHOOT_DECEL
            d = O * (1 - (1 - y) ** 2)
        elif t < c["wound_back"]:
            d = O
        else:
            y = (t - c["wound_back"]) / (c["read_found"] - 0.3 - c["wound_back"])
            d = O * (1 - ease(y))
        di = math.floor(d)
        return x0 + di, d - di, rate

    def uniforms_lehmer(self, s, u):
        t, c = u["t"], self.sync.cues
        L = self.H["lehmer"]
        lay, ys = self.lehmer_layout()
        xi, xf, rate = self.lehmer_x(t)
        t_prev = t - 1 / FPS
        xp, xpf, _ = self.lehmer_x(t_prev)
        speed = abs((xi + xf) - (xp + xpf)) * FPS              # candidates per second right now
        whl = np.zeros((20, 4), "f4"); whl2 = np.zeros((20, 4), "f4")
        I, opens = [1.0], []
        on = float(np.clip((t - s["start"] - 0.3) / 0.8, 0, 1))
        lamp = float(np.clip((t - c["lamp_cell"]) / 0.4, 0, 1))
        for g, (x, y, r, m) in enumerate(lay):
            pos = (xi % m) + xf                                # residue at the beam, plus the turn
            blur = float(np.clip((speed / FPS / m - 0.25) / 0.5, 0, 1))
            whl[g] = (x, y, r, on); whl2[g] = (m, pos, blur, g)
            hole = (xi % m) in set(L["gears"][g]["holes"]) and xf < 0.15
            opens.append(float(hole) * (1 - blur))
        path = list(range(10)) + list(range(19, 9, -1))       # top row rightward, bottom row leftward
        wlit = np.zeros(20, "f4")
        for g in path:
            wlit[g] = I[-1] * lamp
            I.append(I[-1] * opens[g])
        I = np.array(I) * lamp
        flash = float(np.exp(-(t - c["shining"]) / 0.25)) if t >= c["shining"] else 0.0
        steady = I[-1]
        digits = comma(xi)
        cd, nd = codes(digits)
        res = [float(np.clip((t - x) / 0.5, 0, 1)) for x in (c["read_found"], c["read_found"] + 0.6, c["read_found"] + 1.2)]
        return {"whl": whl, "whl2": whl2, "n_whl": 20, "beam_I": I.astype("f4"), "lamp_on": lamp, "wlit": wlit,
                "flash": flash, "steady": float(steady), "x_codes": cd, "x_n": nd, "on": on,
                "beam_y0": ys[0], "beam_y1": ys[1], "speed": float(speed),
                "res_a": np.array(res, "f4"), "cap_a": float(np.clip((t - s["start"]) / 0.6, 0, 1)),
                "t_fair": self.T["fair"], "t_fair2": self.T["fair2"], "t_N": self.T["N19"], "t_x": self.T["x_eq"],
                "t_res": np.array([self.T["res_xy"], self.T["res_pq"], self.T["res_93"]], "f4")}

    # ---------------------------------------------------------------- verse 4: RSA-129, TWINKLE
    def twinkle_state(self, t, t0, n_led_max=40):
        """TWINKLE from t0: one candidate per 1/TWINKLE_DIV beat (on the beat grid); each LED
        p^k flashes on the candidates p^k divides, brightness log p; the summed light against
        log n. Returns (leds (x, y in panel units, brightness, p), candidate, meter, flare)."""
        T = self.H["twinkle"]
        bt = self.sync.beat_t
        half = np.sort(np.r_[bt, 0.5 * (bt[1:] + bt[:-1])]) if TWINKLE_DIV == 2 else bt
        tk = half[half >= t0 - 1e-3]
        j = int(np.searchsorted(tk, t, side="right")) - 1
        leds = np.zeros((n_led_max, 4), "f4")
        primes = sorted({L["p"] for L in T["leds"]})
        for i, L in enumerate(T["leds"]):
            leds[i] = (primes.index(L["p"]), L["k"] - 1, 0.0, L["p"])
        if j < 0:
            return leds, -1, 0.0, 0.0, 0.0, []
        cand = T["candidates"][min(j, len(T["candidates"]) - 1)]
        age = t - tk[j]
        for i in cand["lit"]:
            leds[i, 2] = T["leds"][i]["w"] / math.log(T["bound"]) * (0.35 + 0.65 * math.exp(-age / 0.18))
        meter = cand["sum"] / cand["log"]
        flare = float(cand["smooth"]) * math.exp(-age / 0.22)
        hist = [(T["candidates"][i]["sum"] / T["candidates"][i]["log"], float(T["candidates"][i]["smooth"]))
                for i in range(max(0, j - 23), j + 1)]
        return leds, cand["n"], meter, flare, float(cand["smooth"]), hist

    def uniforms_rsa(self, s, u):
        t, c = u["t"], self.sync.cues
        R = self.H["rsa129"]
        x = (t - c["lock_77"]) / (c["lifetimes"] - 0.4 - c["lock_77"])      # the digits type out
        shown = [float(np.clip(x * 129 - 43 * i, 0, 43)) for i in range(3)]
        mach = float(np.clip((t - c["machines"]) / 2.0, 0, 1)) * R["machines"]
        years = float(np.clip((t - c["seventeen"]) / 0.4, 0, 1))
        # the message, typed over the sung words: "the magic words" then "squeamish ossifrage"
        m1 = float(np.clip((t - c["magic_words"] - 1.30) / (129.34 + 0.4 - c["magic_words"] - 1.30), 0, 1)) * 19
        m2 = float(np.clip((t - c["ossifrage"]) / (131.52 - c["ossifrage"]), 0, 1)) * 19
        fac = float(np.clip((t - c["never_broke"]) / 0.6, 0, 1))
        tw = float(np.clip((t - c["shamir"] + 0.3) / 0.7, 0, 1))
        leds, n, meter, flare, smooth, hist = self.twinkle_state(t, c["shamir"])
        hh = np.zeros((24, 2), "f4")
        for i, h in enumerate(hist[::-1]):
            hh[i] = h
        return {"shown": np.array(shown, "f4"), "mach": mach, "years": years, "m1": m1, "m2": m2, "fac": fac,
                "tw": tw, "leds": leds, "n_led": len(self.H["twinkle"]["leds"]), "cand_n": float(n),
                "meter": float(meter), "flare": float(flare), "is_smooth": smooth, "hist": hh,
                "n_hist": len(hist), "num_a": float(np.clip((t - c["lock_77"] + 0.3) / 0.4, 0, 1)),
                "t_lines": np.array(self.T["rsa_lines"], "f4"), "t_title": self.T["rsa_title"],
                "t_mach": self.T["rsa_machines"], "t_years": self.T["rsa_years"], "t_m1": self.T["msg1"],
                "t_m2": self.T["msg2"], "t_p": self.T["rsa_p"], "t_q": self.T["rsa_q"],
                "t_tw": self.T["tw_title"], "t_sm": self.T["tw_smooth"],
                "primes": np.array(sorted({L["p"] for L in self.H["twinkle"]["leds"]}), "f4")}

    # ---------------------------------------------------------------- bridge: my lamps (tower + split-flap)
    def key_lamps(self, s):
        """Landing time (s from the section start) of each point: the 72, 84 and 96 bands in
        turn, ASSEMBLE_RINGS rings each, one ring per beat, rim first (as tentimesdemo's verse
        1). The spine is there from the start."""
        beats = [b for b in self.sync.beat_t if s["start"] <= b < s["end"]]
        key = np.zeros(len(self.rah), "f4")
        for k, n in enumerate((72, 84, 96)):
            idx = np.nonzero(self.rah[:, 2] == n)[0]
            idx = idx[np.argsort(-self.rah[idx, 0], kind="stable")]
            for j, ring in enumerate(np.array_split(idx, ASSEMBLE_RINGS)):
                b = beats[min(k * ASSEMBLE_RINGS + j, len(beats) - 1)]
                key[ring] = b - s["start"] + 0.12 * self.rah[ring, 1] / (2 * np.pi)
        key[self.attr[:, 0] == 5] = -1.0
        return key

    def camera_lamps(self, s, u):
        az = 0.4 + 0.10 * (u["travel"] - self.sync.at(self.sync.travel, s["start"]))
        return orbit(az, 26.0, self.aspect, dist=CAM_DIST + 0.4, target=(0.0, -0.02, 0.0), shift=0.18)

    def flap_init(self):
        c = self.sync.cues
        self.flips = [self.flip_path([(c["three_point_four"], 3), (c["one_point_four"], 1)]),
                      self.flip_path([(c["three_point_four"] + 0.05, 4)])]

    @staticmethod
    def flip_path(events):
        flips, cur = [], 10
        for t0, target in events:
            k = 0
            while cur != target:
                nxt = 0 if cur == 10 else (cur + 1) % 10
                flips.append((t0 + k * FLIP_DUR, cur, nxt)); cur = nxt; k += 1
        return flips

    @staticmethod
    def flap_state(flips, t):
        a = b = 10; f = 0.0
        for t0, x, y in flips:
            if t < t0:
                break
            a, b, f = x, y, min(1.0, (t - t0) / FLIP_DUR)
        return (b, b, 0.0) if f >= 1.0 else (a, b, f)

    def uniforms_lamps(self, s, u):
        t, c = u["t"], self.sync.cues
        st = [self.flap_state(fl, t) for fl in self.flips]
        g = lambda d: G_BLANK if d == 10 else d
        return {"flap_a": tuple(float(g(x[0])) for x in st), "flap_b": tuple(float(g(x[1])) for x in st),
                "flap_f": tuple(float(x[2]) for x in st),
                "cap_a": float(np.clip((t - c["one_point_four"] - 0.9) / 0.5, 0, 1)), "t_cap": self.T["flap_cap"],
                "settled": float(np.clip((t - c["one_point_four"]) / 0.5, 0, 1))}

    # ---------------------------------------------------------------- "Ten times, not a hundred"
    def uniforms_arms(self, s, u):
        """The 72-bit band: the long arm (stage 2 to 100 B1) sweeps out from the B1 ray on "Ten
        times, not a hundred", lighting its stage-2 points as it passes each one's prime q,
        while its cost bar climbs past the qs line and turns red (+42.8%); on "but not too far"
        the short arm (10 B1) sweeps and relights its own (cost -6.4%). On "the center stays
        dark" the long arm's extra points grey out and the spine brightens grey."""
        n, plong, pshort = ARMS["tentimes"]
        t, c = u["t"], self.sync.cues
        b1 = 9.0
        e0, eL, eS = 1 + b1, 1 + b1 + np.log2(100), 1 + b1 + np.log2(10)
        xl = (t - c["ten_times"]) / (c["reach_out"] - c["ten_times"])
        xs = (t - c["not_too_far"]) / 1.0
        al, as_ = ease(xl), ease(xs)
        scan = -1.0
        if xs >= 1:
            b0 = self.sync.beat(c["not_too_far"] + 1.0)[0]
            scan = e0 + (eS - e0) * ((u["beat"] - b0) / 4.0 % 1.0)
        return {"band_n": float(n), "band_y": (n - 84) / 12 * BAND, "b1_bits": b1, "half_bits": n / 2,
                "arm_e0": e0, "arm_long": e0 + (eL - e0) * al if xl > 0 else 0.0,
                "arm_short": e0 + (eS - e0) * as_ if xs > 0 else 0.0,
                "long_dim": ease((t - c["not_too_far"]) / 0.4),
                "grey": ease((t - c["center_dark"]) / 0.6), "scan": scan,
                "bar_long": (1 + plong / 100) * al, "bar_short": (1 + pshort / 100) * as_,
                "lab_long": ease((t - c["reach_out"]) / 0.15), "lab_short": ease((xs - 1) / 0.15),
                "bars_on": ease(xl * 4), "label_base": 0.0,
                "spine": ease((t - c["center_dark"]) / 0.5) * (1 - 0.5 * ease((t - c["balanced"] - 1.5) / 1.0)),
                "lift": ease((t - s["start"]) / 2.5)}

    def camera_arms(self, s, u):
        """The band at 40 degrees, turned to the wedge; the key change lifts the camera
        LIFT_EL degrees over its first bar."""
        n = u["band_n"]
        a = 2 * np.pi * (u["arm_e0"] + 3.3) / (n / 2)
        az0 = np.arctan2(np.cos(a), -np.sin(a)) + 0.55
        az = az0 + 0.35 * np.sin(0.07 * (u["travel"] - self.sync.at(self.sync.travel, s["start"])))
        el = ARM_EL - LIFT_EL * (1 - u["lift"])
        return orbit(az, el, self.aspect, dist=ARM_DIST, target=(0.0, u["band_y"], 0.0),
                     shift=ARM_SHIFT, inverse=True)

    # ---------------------------------------------------------------- final chorus: everything lit
    def finale_bars(self):
        """The final chorus's bars from its first downbeat (the section start): the layers
        come in one per bar, wheels, LEDs, tower, then the number line."""
        s = self.sync.by_name["final_chorus"]
        bt = self.sync.beat_t
        i0 = int(np.argmin(np.abs(bt - s["start"])))
        return bt[i0::4]

    def big_show(self):
        """The final chorus's sieve: the wheels (2..19) arrive formed on the first bar and land
        one alignment per beat from there; the line 1..400 arrives on the fourth bar with every
        hole open, and the stations strike it from "You build the dark to find the bright" to
        "you pay before you see"."""
        if "final" not in self.shows:
            c, b = self.sync.cues, 60 / self.sync.tempo
            bars = self.finale_bars()
            geo = (BIG_X0, BIG_Y0, LINE_PITCH, BIG_ROW, 100)
            self.shows["final"] = SieveShow(self.sync, self.H["big"], self.H["wheels"]["final"]["alignments"], geo,
                                            FINAL_WHEELS, c["build_dark2"], c["pay_see2"] - 0.12, None,
                                            c["build_dark2"], b / 4, bars[0] + 0.05, bars[0], wheels_in=bars[0])
        return self.shows["final"]

    def uniforms_finale(self, s, u):
        t, c = u["t"], self.sync.cues
        show = self.big_show()
        bars = self.finale_bars()
        lay = [float(np.clip((t - bars[k]) / 0.5, 0, 1)) for k in range(4)]   # wheels, LEDs, tower, line
        C, w = show.state(t, np.full(400, ease(lay[3])), BIG_Y0 + 0.10)
        leds, n, meter, flare, smooth, hist = self.twinkle_state(t, bars[1])
        T = self.H["twinkle"]
        out = dict(w)
        out.update({"tex_cells": C, "line_geo": (BIG_X0, BIG_Y0, LINE_PITCH, BIG_ROW), "line_n": 400.0,
                    "line_cols": 100.0, "cell_aspect": 1.7,
                    "backlight": 0.10 + 0.15 * float(np.clip((t - s["start"]) / 0.5, 0, 1)),
                    "leds": leds, "n_led": len(T["leds"]), "cand_n": float(n), "meter": float(meter),
                    "flare": float(flare), "bloom": 0.9 + 0.9 * u["swell"],
                    "primes": np.array(sorted({L["p"] for L in T["leds"]}), "f4"),
                    "end_a": float(np.clip((s["end"] - t) / 1.5, 0, 1)),
                    "led_a": ease(lay[1]), "tower_a": ease(lay[2]), "line_a": ease(lay[3])})
        return out

    def camera_finale(self, s, u):
        az = 1.1 + FINALE_SPEED * (u["travel"] - self.sync.at(self.sync.travel, s["start"])) / 1.2
        return orbit(az, FINALE_EL, self.aspect, dist=FINALE_DIST, target=(0.0, 0.0, 0.0), shift_y=0.02)

    # ---------------------------------------------------------------- outro
    def uniforms_outro(self, s, u):
        """The sung lines type out word by word over their sung intervals (sections.py
        OUTRO_WORDS) and hold through the full-band tail. The clock steps once per beat of
        the tail (from the last sung word to the last beat, 3:58.47) and stops on the last;
        black from the hard stop."""
        t, c = u["t"], self.sync.cues
        if not hasattr(self, "_ow"):
            self._ow = json.load(open(SECTIONS_JSON))["outro_words"]
        shown = [0, 0]
        for li, line in enumerate(OUTRO_LINES):
            pos = 0
            for w in (x for x in self._ow if x["line"] == li):
                k = line.index(w["word"], pos)
                frac = np.clip((t - w["start"]) / (w["end"] - w["start"]), 0, 1)
                if frac > 0:
                    shown[li] = k + int(np.ceil(frac * len(w["word"])))
                pos = k + len(w["word"])
        bt = self.sync.beat_t
        tail = bt[(bt >= c["tail"]) & (bt <= self.sync.music_end + 1e-3)]
        n_step = int(np.searchsorted(tail, t, side="right"))
        since = float(t - tail[n_step - 1]) if n_step else 1e3
        C = np.zeros((1, 100, 4), "f4"); C[0, :, 0] = 1.0; C[0, :, 1] = 1.0
        surv = np.array(self.H["line"]["survivors"]) - 1
        C[0, surv, 1] = 0.0
        C[0, surv, 3] = 0.55 * float(np.clip((t - s["start"]) / 1.0, 0, 1)) + 0.25 * float(np.exp(-since / 0.25)) * float(n_step > 0)
        last_end = self._ow[-1]["end"]
        return {"len0": float(len(OUTRO_LINES[0])), "len1": float(len(OUTRO_LINES[1])),
                "shown0": float(shown[0]), "shown1": float(shown[1]),
                "t_l0": self.T["outro"][0], "t_l1": self.T["outro"][1],
                "typing": float(t < last_end), "n_step": float(n_step), "since_step": since,
                "steps_total": float(len(tail)), "stopped": float(t >= tail[-1]),
                "black": float(t >= self.sync.hard_stop),
                "tex_cells": C, "line_geo": (LINE_X0, LINE_Y["outro"], LINE_PITCH, 0.0), "line_n": 100.0,
                "line_cols": 100.0, "cell_aspect": 1.7, "backlight": 0.06,
                "clock_a": float(np.clip((t - c["tail"] + 0.6) / 0.6, 0, 1))}

    # ---------------------------------------------------------------- the frame
    def frame(self, fi):
        t = fi / FPS
        s = self.sync.section(t)
        name = self.scene or s["scene"]
        u = dict(self.sync.uniforms(t), **self.atlas_u)
        extra = getattr(self, "uniforms_" + name, None)
        if extra:
            u.update(extra(s, u))
        cam = getattr(self, "camera_" + name, None)
        if cam:
            m = cam(s, u)
            if isinstance(m, tuple):
                u["view_proj"], u["inv_view_proj"] = m
            else:
                u["view_proj"] = m
            if name == "finale":
                u["cam_dist"] = FINALE_DIST
        kf = getattr(self, "keyframe_" + name, None)
        key = kf(s, u) if kf else self.key(dict(s, scene=name))
        bg = (0.0, 0.0, 0.0) if t >= self.sync.hard_stop else BG
        return self.r.frame(name, u, fi, key=key, bloom_gain=u.get("bloom", 0.9), bg=bg)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="'-' renders stills only")
    ap.add_argument("--audio", default="", help="the song's WAV ('' for a silent clip)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--section", default=None, help="render exactly this section (by name)")
    ap.add_argument("--full", action="store_true", help="the whole film: 0 to the song's end")
    ap.add_argument("--res", type=int, default=1080, choices=(480, 720, 1080, 2160))
    ap.add_argument("--scene", default=None, help="force one scene (else the section map)")
    ap.add_argument("--crf", type=int, default=22, help="22 for previews; 16 for the 4K master")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--still", action="append", type=float, default=[],
                    help="also save the frame at this time as PNG (repeatable)")
    ap.add_argument("--stem", default=None, help="stills: path prefix (default renders/still)")
    a = ap.parse_args()

    H = a.res; W = int(round(H * 16 / 9 / 2)) * 2
    film = Film(W, H, a.scene)
    if a.full:
        f0, n = 0, film.sync.n_frames
    elif a.section:
        s = film.sync.by_name[a.section]
        f0 = int(np.ceil(s["start"] * FPS - 1e-9)); n = int(np.ceil(s["end"] * FPS - 1e-9)) - f0
    else:
        f0, n = round(a.start * FPS), round(a.dur * FPS)
    stills = {round(t * FPS): t for t in a.still}
    stem = a.stem or (os.path.splitext(a.out)[0] if a.out != "-" else os.path.join(HERE, "renders", "still"))
    os.makedirs(os.path.dirname(os.path.abspath(stem)), exist_ok=True)
    if a.out == "-":
        print(f"stills {W}x{H}: {', '.join(f'{t:.2f}' for t in sorted(a.still))} s", file=sys.stderr)
        for fi, t in sorted(stills.items()):
            save_png(film.frame(fi), W, H, f"{stem}_{t:06.2f}s.png")
        return
    print(f"render {W}x{H} @ {FPS} fps: frames {f0}..{f0 + n - 1} ({n} frames, "
          f"{f0 / FPS:.3f}-{(f0 + n) / FPS:.3f} s), scene {a.scene or 'by section'}", file=sys.stderr)
    proc = ffmpeg_writer(a.out, W, H, f0 / FPS, n / FPS, a.audio, a.crf, a.preset, film.sync.duration)
    for fi in range(f0, f0 + n):
        buf = film.frame(fi)
        proc.stdin.write(buf)
        if fi in stills:
            save_png(buf, W, H, f"{stem}_{stills[fi]:06.2f}s.png")
        if (fi - f0) % 300 == 0:
            print(f"frame {fi} / {f0 + n} ({fi / FPS:.1f} s)", file=sys.stderr, flush=True)
    proc.stdin.close()
    sys.exit(proc.wait())

if __name__ == "__main__":
    main()
