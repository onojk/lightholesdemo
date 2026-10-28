// Bridge: the tower assembles (as tentimesdemo's verse 1), one ring per beat, rim first; key
// = landing time (s from the section start; render.py key_lamps). Each point drops in, flashes
// as it lands, and lights in its first lamp's colour; the dark points (left to qs) stay grey,
// and so does the spine: the wall.
const float FALL = 0.45;

void main() {
    float lamp = attr.x;
    vec3 w = world(rah);
    if (lamp > 4.5) { place(w, 0.85); v_col = DARK; v_a = 0.6; return; }
    float age = ts - key;
    if (age < -FALL) { hide(); return; }
    float fall = clamp(-age / FALL, 0.0, 1.0);
    w.y += 0.7 * fall * fall;
    float land = age >= 0.0 ? exp(-age / 0.15) : 0.0;
    vec3 lc = lamp < 0.5 ? TD * 1.5 : lamp < 1.5 ? RHO * 1.6 : lamp < 2.5 ? PM1 * 2.0 : lamp < 3.5 ? PM2 * 1.5 : DARK * 0.8;
    vec3 c = mix(DARK * 0.9, lc, smoothstep(0.1, 0.5, age));
    v_col = c + WHITE * 0.4 * land;
    v_a = (1.0 - fall) * (1.0 + 0.3 * kick);
    place(w, 1.0);
}
