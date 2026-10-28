// Final chorus: everything lit at once (render.py uniforms_finale). The tower turns in the
// middle (finale.pts.glsl; the spine stays grey). Along the bottom, 1..400 in four rows: on
// "the stations walk the line" stations 2..19 sweep from p^2; on "every gear in its own time"
// each period curls into a wheel and flies to the row at the top; from "wait until they all
// align" the eight wheels land on one alignment per beat (23, 29, 31, ...: no factor up to 19)
// and the beam reaches the cell. At left TWINKLE's LEDs run on (lib_twinkle.glsl), the meter at
// right. Bloom rides the choir swell.
#include "lib_sieve.glsl"
#include "lib_twinkle.glsl"
uniform float end_a;

void main() {
    vec2 p = P();
    vec3 c = line_col(p, CYAN * 1.1 + WHITE * 0.3);
    c += stations_col(p);
    c = sieve_machine(p, c);
    c += twinkle_panel(p, vec2(-1.72, -0.38), 0.056, 1.0);
    c += twinkle_meter(p, vec2(1.62, -0.42), 0.80, 0.030, 1.0);
    if (cand_n > 0.0) c += mix(CYAN * 0.8, GREEN * 1.4, flare) * gnum(cand_n, p, vec2(1.62, -0.52), 0.032);
    frag = vec4(c * end_a, 1.0);
}
