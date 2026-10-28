// Verse 2 (render.py uniforms_legendre).
// Legendre's abacus for x = 100 with the stations 2, 3, 5, 7: one row per number of primes in
// the subset; one bead per multiple (floor(100 / d)), grouped by d. Rows with sign + glow,
// rows with sign - are grey rings: taken away. Rows appear on "Legendre's ledger / took away
// and then put back / plus and minus on an abacus", the sum on "to keep the count on track":
// 100 - 117 + 45 - 6 + 0 = 22, with the 22 numbers listed.
// The Wander: M(n) for n to 10,000 (data/holes.json), drawn left to right from "the signs
// began to wander"; the +-sqrt(n) envelope on "how far they can stray"; on "Selberg found the
// wall" a grey wall rises at its end. On "one floor from two": 139 (one floor) and
// 143 = 11 x 13 (two floors) behind the same grey: a sieve to 10 sees the same stone.
uniform float row_a[5], grp[40], gd[40], ng[5], t_rows[5];
uniform float total, fade_ab, walk_on, walk, env, wall, towers, par;
uniform float t_total, t_title, t_list, t_list2, t_walk, t_env, t_end, t_wall, t139, t143, t_floors, t_par;
uniform sampler2D walk_tex;

const float BP = 0.0118, GG = 0.034;            // bead pitch, group gap
const float WX0 = -1.55, WX1 = 1.30, WY = 0.30, WS = 0.0045;   // the Wander's box, scale per unit

vec3 abacus(vec2 p) {
    vec3 c = vec3(0.0);
    float aa = px();
    for (int i = 0; i < 5; i++) {
        if (row_a[i] <= 0.0) continue;
        float y = 0.56 - 0.17 * float(i);
        float sgn = mod(float(i), 2.0) < 0.5 ? 1.0 : -1.0;
        int n = int(ng[i]);
        float width = 0.0, total_b = 0.0;
        for (int j = 0; j < 8; j++) { if (j >= n) break; width += grp[i * 8 + j] * BP; total_b += grp[i * 8 + j]; }
        width += GG * float(max(n - 1, 0));
        float x = -0.20 - 0.5 * width, seen = 0.0;
        for (int j = 0; j < 8; j++) {
            if (j >= n) break;
            float cnt = grp[i * 8 + j];
            float k = floor((p.x - x) / BP);
            if (k >= 0.0 && k < cnt && seen + k < row_a[i] * total_b) {
                vec2 bc = vec2(x + (k + 0.5) * BP, y);
                float r = length(p - bc);
                if (sgn > 0.0) c += (TEAL * 1.1 + CYAN * 0.3) * smoothstep(0.0048 + aa, 0.0048 - aa, r);
                else c += DARK * 0.9 * smoothstep(0.0012 + aa, 0.0012 - aa, abs(r - 0.0040));
            }
            c += DARK * 1.1 * row_a[i] * gnum(gd[i * 8 + j], p, vec2(x + 0.5 * cnt * BP, y - 0.040), 0.013);
            seen += cnt;
            x += cnt * BP + GG;
        }
        vec3 lc = sgn > 0.0 ? CYAN : DARK * 1.4;
        c += lc * row_a[i] * atext(t_rows[i], p, vec2(1.42, y), 0.030, -1.0);
    }
    c += CYAN * atext(t_title, p, vec2(0.0, 0.84), 0.028, -1.0) * row_a[0];
    c += GREEN * 1.2 * total * atext(t_total, p, vec2(0.0, -0.36), 0.040, -1.0);
    c += TEAL * 1.1 * total * atext(t_list, p, vec2(0.0, -0.52), 0.026, -1.0);
    c += TEAL * 1.1 * total * atext(t_list2, p, vec2(0.0, -0.60), 0.026, -1.0);
    return c;
}

vec3 wander(vec2 p) {
    vec3 c = vec3(0.0);
    float aa = px();
    float fx = (p.x - WX0) / (WX1 - WX0);
    if (fx >= 0.0 && fx < 1.0) {
        int col = int(fx * 1600.0);
        vec4 w = texelFetch(walk_tex, ivec2(col, 0), 0);
        // the zero line
        c += DEEP * 0.9 * exp(-pow((p.y - WY) / (1.0 * aa), 2.0));
        if (fx < walk) {
            float lo = WY + w.x * WS, hi = WY + w.y * WS;
            float d = max(max(lo - p.y, p.y - hi), 0.0);
            c += (TEAL * 1.2 + CYAN * 0.4) * (exp(-d * d / (1.6 * aa * aa)) + 0.2 * exp(-d * d / (36.0 * aa * aa)));
            float head = exp(-pow((fx - walk) * 1600.0 / 6.0, 2.0));
            c += WHITE * 0.8 * head * exp(-d * d / (9.0 * aa * aa));
        }
        if (fx < env) {
            float e = w.z * WS;
            float dash = step(0.5, fract(fx * 160.0));
            c += CYAN * 0.45 * dash * (exp(-pow((p.y - WY - e) / (1.2 * aa), 2.0)) + exp(-pow((p.y - WY + e) / (1.2 * aa), 2.0)));
        }
    }
    c += CYAN * 0.9 * walk_on * atext(t_walk, p, vec2(0.0, 0.86), 0.026, -1.0);
    c += CYAN * 0.8 * env * atext(t_env, p, vec2(WX1 - 0.12, WY + 100.0 * WS + 0.05), 0.026, -1.0);
    c += TEAL * 1.1 * step(0.999, walk) * atext(t_end, p, vec2(WX1 - 0.25, WY - 0.30), 0.024, -1.0);
    // the wall at the walk's end
    if (wall > 0.0) {
        float x0 = WX1 + 0.025, x1 = WX1 + 0.12;
        float yb = WY - 0.50, yt = yb + 1.0 * wall;
        float inside = step(x0, p.x) * step(p.x, x1) * step(yb, p.y) * step(p.y, yt);
        c = mix(c, DARK * 0.55, inside);
        c += DARK * 0.8 * inside * smoothstep(x0 + 3.0 * aa, x0, p.x);
        c += DARK * 1.3 * wall * atext(t_wall, p, vec2(WX1 - 0.32, WY - 0.38), 0.024, -1.0);
    }
    return c;
}

vec3 tower2(vec2 p, float x, float floors, float a) {
    float aa = px();
    float y0 = -0.95, h = 0.30, hw = 0.13;
    vec2 q = p - vec2(x, y0 + 0.5 * h);
    float box = smoothstep(aa, -aa, max(abs(q.x) - hw, abs(q.y) - 0.5 * h));
    float edge = smoothstep(2.0 * aa, 0.0, abs(max(abs(q.x) - hw, abs(q.y) - 0.5 * h)));
    vec3 c = TEAL * 0.35 * box + CYAN * 0.9 * edge;
    if (floors > 1.5) c += CYAN * 0.9 * step(abs(q.x), hw) * smoothstep(2.0 * aa, 0.0, abs(q.y));
    // the sieve's grey up to the top of what it can see: both towers read as one block
    float grey = step(abs(q.x), hw + 0.02) * step(p.y, y0 + h * 0.92) * step(y0, p.y);
    c = mix(c, DARK * 0.55, 0.88 * grey * par);
    return c * a;
}

void main() {
    vec2 p = P();
    vec3 c = abacus(p) * (1.0 - fade_ab);
    if (walk_on > 0.5) c += wander(p);
    if (towers > 0.0) {
        c += tower2(p, -0.45, 1.0, towers) + tower2(p, 0.45, 2.0, towers);
        c += CYAN * towers * atext(t139, p, vec2(-0.45, -0.57), 0.028, -1.0);
        c += CYAN * towers * atext(t143, p, vec2(0.45, -0.57), 0.028, -1.0);
        c += DARK * 1.4 * par * atext(t_par, p, vec2(0.0, -0.36), 0.024, -1.0);
    }
    frag = vec4(c, 1.0);
}
