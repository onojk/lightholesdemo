// Verse 3: the photoelectric sieve, 1933 (render.py uniforms_lehmer).
// Twenty gears for N = 1,537,228,672,093,301,419 (2^93 + 1 without 3^2 and 715,827,883), each
// a prime modulus m drilled at the x for which x^2 - N is a square mod m (data/holes.json).
// The lamp's beam runs right along the top row, down a mirror, and left along the bottom row
// to the cell. The machine turns at about 5,000 candidates a second (the gears blur); on "the
// light came shining through" every hole lines up at x = (p + q) / 2 and the cell flashes; it
// coasts past (the overshoot); on "wound it back by hand" it turns back to the answer, and
// the light stays on. On "to read what it had found": x and y, then p and q.
uniform vec4 whl[20], whl2[20];
uniform float wlit[20];
uniform float beam_I[21];
uniform float lamp_on, flash, steady, on, beam_y0, beam_y1, speed, cap_a;
uniform float x_codes[32];
uniform int x_n;
uniform float res_a[3], t_res[3];
uniform float t_fair, t_fair2, t_N, t_x;

const float XL = -1.70, XR = 1.70;

float I(int k) { return max(beam_I[k], flash); }

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    float w = 1.8 * px();
    float fl = 1.0 + 2.5 * flash;
    // the beam path (under the gears)
    vec3 b = vec3(0.0);
    b += beam(p, vec2(XL, beam_y0), vec2(whl[0].x, beam_y0), I(0), w);
    for (int k = 1; k < 10; k++) b += beam(p, vec2(whl[k - 1].x, beam_y0), vec2(whl[k].x, beam_y0), I(k), w);
    b += beam(p, vec2(whl[9].x, beam_y0), vec2(XR, beam_y0), I(10), w);
    b += beam(p, vec2(XR, beam_y0), vec2(XR, beam_y1), I(10), w);
    b += beam(p, vec2(XR, beam_y1), vec2(whl[19].x, beam_y1), I(10), w);
    for (int j = 1; j < 10; j++) b += beam(p, vec2(whl[20 - j].x, beam_y1), vec2(whl[19 - j].x, beam_y1), I(10 + j), w);
    b += beam(p, vec2(whl[10].x, beam_y1), vec2(XL, beam_y1), I(20), w);
    c += b * fl * lamp_on;
    // the gears
    for (int g = 0; g < 20; g++) {
        vec4 wv = wheel(p, whl[g].xy, whl[g].z, whl2[g].x, whl2[g].y, 1.0, whl2[g].w, whl2[g].z, wlit[g] * fl, whl[g].w);
        c = c * (1.0 - wv.a) + wv.rgb;
        c += DARK * 1.0 * whl[g].w * gnum(whl2[g].x, p, whl[g].xy - vec2(0.0, 0.42 * whl[g].z), 0.28 * whl[g].z);
    }
    // lamp, mirror, cell
    vec2 LP = vec2(XL, beam_y0), CP = vec2(XL, beam_y1);
    c += (WHITE * 0.7 + CYAN * 0.4) * lamp_on * (smoothstep(0.026, 0.020, length(p - LP)) + 0.4 * glow(length(p - LP), 0.03));
    float h;
    c += DARK * 1.2 * on * smoothstep(2.0 * px(), 0.0, seg(p, vec2(XR - 0.03, beam_y0 + 0.03), vec2(XR + 0.03, beam_y0 - 0.03), h));
    c += DARK * 1.2 * on * smoothstep(2.0 * px(), 0.0, seg(p, vec2(XR - 0.03, beam_y1 - 0.03), vec2(XR + 0.03, beam_y1 + 0.03), h));
    vec2 q = abs(p - CP);
    float cellv = max(I(20), steady);
    c += step(q.x, 0.022) * step(q.y, 0.05) * (DEEP * 0.9 + (GREEN * 1.4 + WHITE * 0.6) * cellv * fl) * on;
    c += GREEN * 0.6 * cellv * fl * glow(length(p - CP), 0.06) * on;
    // captions and the counter
    c += CYAN * cap_a * atext(t_fair, p, vec2(0.0, 0.90), 0.030, -1.0);
    c += DARK * 1.3 * cap_a * atext(t_fair2, p, vec2(0.0, 0.825), 0.022, -1.0);
    c += TEAL * 1.1 * cap_a * atext(t_N, p, vec2(0.0, 0.70), 0.026, -1.0);
    c += CYAN * on * atext(t_x, p, vec2(-0.33, 0.58), 0.030, -1.0);
    c += (CYAN * 0.9 + GREEN * 0.6 * cellv) * on * gcodes(x_codes, x_n, p, vec2(0.0, 0.58), 0.032);
    // what it had found
    c += GREEN * 1.1 * res_a[0] * atext(t_res[0], p, vec2(0.0, -0.58), 0.030, -1.0);
    c += GREEN * 1.3 * res_a[1] * atext(t_res[1], p, vec2(0.0, -0.70), 0.030, -1.0);
    c += CYAN * 1.0 * res_a[2] * atext(t_res[2], p, vec2(0.0, -0.84), 0.026, -1.0);
    frag = vec4(c, 1.0);
}
