// Bridge, "So I built my lamps on a laptop" (render.py uniforms_lamps): the theta tower from
// tentimesdemo assembles behind (lamps.pts.glsl). At upper left a split-flap counter: blank ->
// 3.4 on "the formula said three-point-four", then 3 -> 4 -> ... -> 0 -> 1 on "the primes came
// back around"; "fitted c = 1.41" under it (tentimesdemo: NOTES, real-prime measurement run).
uniform vec2 flap_a, flap_b, flap_f;
uniform float cap_a, t_cap, settled;

const float CW = 0.13, CH = 0.19;
const vec2 C0 = vec2(-1.40, 0.56), C1 = vec2(-1.05, 0.56);

vec3 card(vec2 q, float a, float b, float f) {
    vec3 bg = DEEP * 0.35;
    float g, shade = 1.0;
    if (q.y >= 0.0) {
        float hy = cos(PI * f);
        if (f < 0.5 && q.y < hy) { g = gcell(a, vec2(q.x, q.y / hy)); shade = 0.55 + 0.45 * hy; }
        else g = gcell(b, q);
    } else {
        float hy = -cos(PI * f);
        if (f >= 0.5 && -q.y < hy) { g = gcell(b, vec2(q.x, q.y / hy)); shade = 0.55 + 0.45 * hy; }
        else g = gcell(a, q);
    }
    vec3 c = (bg + mix(CYAN, GREEN, settled) * 1.1 * g) * shade;
    c *= smoothstep(0.0, 0.035, abs(q.y));
    return c * smoothstep(1.0, 0.97, max(abs(q.x), abs(q.y)));
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    vec2 q0 = (p - C0) / vec2(CW, CH), q1 = (p - C1) / vec2(CW, CH);
    bool shown = flap_b.x < 15.5 || flap_a.x < 15.5;
    if (shown && abs(q0.x) <= 1.0 && abs(q0.y) <= 1.0) c += card(q0, flap_a.x, flap_b.x, flap_f.x);
    if (shown && abs(q1.x) <= 1.0 && abs(q1.y) <= 1.0) c += card(q1, flap_a.y, flap_b.y, flap_f.y);
    if (shown) c += WHITE * 0.9 * smoothstep(0.022, 0.016, length(p - vec2(0.5 * (C0.x + C1.x), C0.y - CH + 0.03)));
    c += GREEN * 0.9 * cap_a * atext(t_cap, p, vec2(0.5 * (C0.x + C1.x), C0.y - CH - 0.09), 0.030, -1.0);
    frag = vec4(c, 1.0);
}
