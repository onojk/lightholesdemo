// The 0:37 break (the guitar-solo slot): the sieve of Eratosthenes at high speed on 1..10,000,
// a 100 x 100 grid. Each onset brings the next station down on the whole grid at once; the
// cells it strikes first flash and shut. Station 2 shuts half the grid, so its flash is
// scaled down to a fixed share of the frame (render.py FLASH_AREA). Then the 1,229 survivors
// glow (render.py uniforms_strobe).
uniform float p_now, p_a, k_now, done, t_count, t_title;

void main() {
    vec2 p = P();
    vec3 sc = station_col(k_now);
    vec3 c = line_col(p, sc * 0.9 + WHITE * 0.3);
    // the station now striking, large, at left
    c += sc * 1.2 * p_a * gnum(p_now, p, vec2(-1.33, 0.06), 0.12);
    c += DARK * 1.2 * atext(t_title, p, vec2(-1.33, -0.16), 0.024, -1.0);
    c += GREEN * 1.1 * done * atext(t_count, p, vec2(1.33, 0.0), 0.022, -1.0);
    frag = vec4(c, 1.0);
}
