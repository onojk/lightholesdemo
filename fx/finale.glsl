// Final chorus: everything lit at once, the layers coming in one per bar from its first
// downbeat (render.py uniforms_finale): the eight wheels (2..19) fall into their row at the
// top and land one alignment per beat (1, 23, 29, 31, ...: no factor up to 19), the beam
// reaching the cell; TWINKLE's LEDs at left with the meter at right (lib_twinkle.glsl); the
// tower in the middle (finale.pts.glsl; the spine stays grey); then 1..400 in four rows along
// the bottom, struck by stations 2..19 on "You build the dark to find the bright". Bloom
// rides the choir swell.
#include "lib_sieve.glsl"
#include "lib_twinkle.glsl"
uniform float end_a, led_a, tower_a, line_a;

void main() {
    vec2 p = P();
    vec3 c = line_col(p, CYAN * 1.1 + WHITE * 0.3);
    c += stations_col(p) * line_a;
    c = sieve_machine(p, c);
    c += twinkle_panel(p, vec2(-1.72, -0.38), 0.056, led_a);
    c += twinkle_meter(p, vec2(1.62, -0.42), 0.80, 0.030, led_a);
    if (cand_n > 0.0) c += led_a * mix(CYAN * 0.8, GREEN * 1.4, flare) * gnum(cand_n, p, vec2(1.62, -0.52), 0.032);
    frag = vec4(c * end_a, 1.0);
}
