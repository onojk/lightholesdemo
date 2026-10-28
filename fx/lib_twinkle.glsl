// Shared by rsa.glsl and finale.glsl: TWINKLE's LEDs (render.py twinkle_state). One LED per
// prime power p^k (p <= 31): a column per prime, a row per power. Each flashes on the
// candidates p^k divides, brightness log p; a meter sums the light against log n; at a smooth
// candidate the sum reaches log n and the panel flares.
uniform vec4 leds[40];                // column, row, brightness, p
uniform int n_led;
uniform float primes[11];
uniform float cand_n, meter, flare;

// the panel with its origin (bottom-left LED) at o, LED pitch s
vec3 twinkle_panel(vec2 p, vec2 o, float s, float a) {
    vec3 c = vec3(0.0);
    float aa = px();
    vec2 q = (p - o) / s;
    float col = floor(q.x + 0.5), row = floor(q.y + 0.5);
    for (int i = 0; i < 40; i++) {
        if (i >= n_led) break;
        if (abs(leds[i].x - col) > 0.5 || abs(leds[i].y - row) > 0.5) continue;
        vec2 lc = o + s * leds[i].xy;
        float r = length(p - lc);
        float b = leds[i].z;
        vec3 sc = station_col(leds[i].x);
        c += DEEP * 0.8 * smoothstep(0.30 * s + aa, 0.30 * s - aa, r);
        c += sc * 2.2 * b * (smoothstep(0.28 * s + aa, 0.28 * s - aa, r) + 0.6 * exp(-r * r / (0.25 * s * s)));
    }
    for (int k = 0; k < 11; k++)
        c += DARK * 1.2 * gnum(primes[k], p, o + s * vec2(float(k), -0.85), 0.24 * s);
    return c * a;
}

// the meter: a bar of height ∝ meter (the light / log n), the log n line at full height
vec3 twinkle_meter(vec2 p, vec2 base, float hgt, float wdt, float a) {
    vec3 c = vec3(0.0);
    vec2 q = p - base;
    float aa = px();
    if (abs(q.x) < wdt && q.y > 0.0 && q.y < hgt * meter)
        c += mix(TEAL * 0.8, GREEN * 1.6 + WHITE * 0.6, flare);
    if (abs(q.x) < wdt * 1.6) c += WHITE * 0.6 * exp(-pow((q.y - hgt) / (1.2 * aa), 2.0));
    c += (GREEN * 0.8 + WHITE * 0.3) * flare * glow(length(q - vec2(0.0, hgt)), 0.06);
    return c * a;
}
