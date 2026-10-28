// Intro, pre-chorus, chorus 1 (render.py uniforms_sieve):
//   intro      the number line 1..100 ticks in, a decade per half beat
//   pre-chorus grey static on "No one asked the survivors"; on "known by what was missed" it
//              clears: the struck cells are shut, and the 25 survivors (the primes) glow
//   chorus 1   every hole opens again and the line drops; on "the stations walk the line"
//              stations 2, 3, 5, 7 stride from p^2, striking; on "every gear in its own time"
//              each station's period curls into a ring and becomes a wheel; from "wait until
//              they all align" the wheels land on one alignment per beat (11, 13, ... 97),
//              and the beam reaches the cell
#include "lib_sieve.glsl"
uniform float static_a, glow_pr, lab_a, tick, surv_a, t_surv, chorus;
uniform float decades[11];

bool is_prime(float n) {
    if (n < 2.0) return false;
    for (float d = 2.0; d * d <= n; d += 1.0)
        if (abs(n - d * floor(n / d + 0.5)) < 0.5) return false;   // float mod can round to d
    return true;
}

void main() {
    vec2 p = P();
    vec3 c = line_col(p, CYAN * 1.1 + WHITE * 0.3);
    float y = line_geo.y, pitch = line_geo.z;

    // decade labels under the line
    if (lab_a > 0.0)
        for (int k = 0; k < 11; k++) {
            float n = k == 0 ? 1.0 : 10.0 * float(k);
            c += DARK * 1.3 * lab_a * atext(decades[k], p, vec2(line_geo.x + (n - 0.5) * pitch, y - 0.068), 0.020, -1.0);
        }

    // the survivors' numbers over their cells, and the caption
    if (surv_a > 0.0) {
        float col = floor((p.x - line_geo.x) / pitch), n = col + 1.0;
        if (col >= 0.0 && col < 100.0 && is_prime(n)) {
            float hi = is_prime(n - 1.0) ? 0.034 : 0.0;          // 3 sits next to 2
            c += GREEN * 1.1 * surv_a * gnum(n, p, vec2(line_geo.x + (col + 0.5) * pitch, y + 0.062 + hi), 0.014);
        }
        c += CYAN * 0.8 * surv_a * atext(t_surv, p, vec2(0.0, y - 0.16), 0.028, -1.0);
    }

    c += stations_col(p);
    if (chorus > 0.5) c = sieve_machine(p, c);

    // grey static: strongest over the line
    if (static_a > 0.0) {
        float f = floor(t * 30.0);
        vec2 g = floor(gl_FragCoord.xy / 2.0);
        uint hk = uint(g.x) + 1931u * uint(g.y) + 104729u * uint(f);   // integer: floats above 2^24 smear
        float nz = float(hash(hk ^ uint(seed))) / 4294967295.0;
        float band = 0.35 + 0.65 * exp(-pow((p.y - y) / 0.25, 2.0));
        c = mix(c, DARK * (0.15 + 0.85 * nz) * 0.75, static_a * band);
    }
    frag = vec4(c, 1.0);
}
