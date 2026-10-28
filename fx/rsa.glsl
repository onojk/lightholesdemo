// Verse 4 (render.py uniforms_rsa).
// RSA-129: its 129 digits type out on "they rolled a lock in '77"; 1,600 machines light on
// "sixteen hundred machines"; "1977 -> 1994" on "seventeen years"; the message types on the
// sung words "the magic words / squeamish ossifrage"; on "they never broke the wall, they
// only paid its wage" the number splits into its two factors (64 and 65 digits).
// TWINKLE from "Shamir dreamed of diodes" (lib_twinkle.glsl): the LEDs flash on the
// candidates 1000, 1001, ..., one per eighth note; the meter flares when the light adds up to
// log n, at the 31-smooth candidates; the last 24 candidates scroll along the bottom.
#include "lib_twinkle.glsl"
uniform float shown[3], t_lines[3];
uniform float mach, years, m1, m2, fac, tw, num_a, is_smooth;
uniform vec2 hist[24];
uniform int n_hist;
uniform float t_title, t_mach, t_years, t_m1, t_m2, t_p, t_q, t_tw, t_sm;

vec3 rsa(vec2 p) {
    vec3 c = vec3(0.0);
    float aa = px();
    c += CYAN * num_a * atext(t_title, p, vec2(0.0, 0.88), 0.028, -1.0);
    vec3 nc = mix(CYAN * 0.9, DARK * 0.9, fac);
    for (int i = 0; i < 3; i++)
        c += nc * atext(t_lines[i], p, vec2(0.0, 0.70 - 0.11 * float(i)), 0.040, shown[i]);
    // 1,600 machines: a 40 x 40 grid of points, lit in order
    vec2 g0 = vec2(-1.30, -0.22);
    vec2 q = (p - g0) / 0.0112;
    float gx = floor(q.x + 0.5), gy = floor(q.y + 0.5);
    if (gx >= 0.0 && gx < 40.0 && gy >= 0.0 && gy < 40.0) {
        float idx = gy * 40.0 + gx;
        float r = length(q - vec2(gx, gy)) * 0.0112;
        float on_ = step(idx, mach - 0.5);
        c += mix(DEEP * 0.5 * step(0.5, mach), GREEN * 0.9 + TEAL * 0.3, on_) * smoothstep(0.0036 + aa, 0.0036 - aa, r);
    }
    c += GREEN * step(1.0, mach) * atext(t_mach, p, vec2(-1.08, -0.31), 0.026, -1.0);
    c += CYAN * years * atext(t_years, p, vec2(0.75, 0.0), 0.030, -1.0);
    // the message
    c += WHITE * 0.95 * atext(t_m1, p, vec2(0.62, -0.30), 0.042, m1);
    c += (WHITE * 0.95 + GREEN * 0.3) * atext(t_m2, p, vec2(0.62, -0.42), 0.042, m2);
    // the factors
    c += GREEN * 1.2 * fac * atext(t_p, p, vec2(0.0, -0.66), 0.026, -1.0);
    c += GREEN * 1.2 * fac * atext(t_q, p, vec2(0.0, -0.75), 0.026, -1.0);
    return c;
}

vec3 twinkle(vec2 p) {
    vec3 c = CYAN * atext(t_tw, p, vec2(0.0, 0.88), 0.026, -1.0);
    c += twinkle_panel(p, vec2(-1.45, -0.42), 0.115, 1.0);
    c += twinkle_meter(p, vec2(0.55, -0.48), 0.95, 0.045, 1.0);
    if (cand_n > 0.0) c += mix(CYAN * 0.9, GREEN * 1.5, is_smooth) * gnum(cand_n, p, vec2(1.18, 0.05), 0.09);
    c += GREEN * 1.2 * is_smooth * atext(t_sm, p, vec2(1.18, -0.12), 0.022, -1.0);
    // the last 24 candidates, newest at the right
    float aa = px();
    for (int i = 0; i < 24; i++) {
        if (i >= n_hist) break;
        float x = 1.62 - 0.135 * float(i);
        vec2 q = p - vec2(x, -0.93);
        if (abs(q.x) < 0.045 && q.y > 0.0 && q.y < 0.20 * hist[i].x)
            c += mix(DEEP * 1.2, GREEN * 1.3, hist[i].y) * (i == 0 ? 1.3 : 0.8);
    }
    return c;
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    if (tw < 1.0) c += rsa(p) * (1.0 - tw);
    if (tw > 0.0) c += twinkle(p) * tw;
    frag = vec4(c, 1.0);
}
