// Shared by sieve.glsl (intro, pre-chorus, chorus 1) and finale.glsl: the stations striding
// on the line, a station's period curling into a ring, the wheels it becomes, and the beam
// from the lamp through every wheel's top hole to the photocell (render.py SieveShow).
uniform vec4 sta[8];                  // per station: cell index (0-based), alpha, p, colour k
uniform int n_sta;
uniform vec4 strip[8], strip2[8];     // bend w, anchor x, y, scale / m, alpha
uniform int n_strip;
uniform vec4 whl[8], whl2[8];         // centre x, y, radius, alpha / m, pos, blur, light in its top hole
uniform int n_whl;
uniform float beam_I[9];              // light reaching wheel k (k = n_whl: the cell)
uniform float lamp_on, land_flash, cand, cand_a, beam_y, lamp_x, cell_x;

vec3 stations_col(vec2 p) {
    vec3 c = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        if (i >= n_sta) break;
        float ci = sta[i].x, a = sta[i].y;
        float row = floor(ci / line_cols), col = ci - row * line_cols;
        vec2 cc = vec2(line_geo.x + (col + 0.5) * line_geo.z, line_geo.y - row * line_geo.w);
        vec3 sc = station_col(sta[i].w);
        // the strider: a bright wedge pointing down at its cell
        vec2 q = p - (cc + vec2(0.0, 0.5 * line_geo.z * cell_aspect + 0.022));
        float tri = step(q.y, 0.016) * step(-0.012, q.y) * step(abs(q.x), 0.4 * (q.y + 0.012));
        c += sc * 1.4 * a * tri;
        c += sc * 0.9 * a * gnum(sta[i].z, p, cc + vec2(0.0, 0.5 * line_geo.z * cell_aspect + 0.062), 0.022);
    }
    return c;
}

// one station's period: m cells (residues 1..m-1 open, residue 0 struck, at the right end),
// bent by w into a ring (w = 1)
vec3 strip_col(vec2 p, vec4 S, vec4 S2) {
    float w = S.x, sc = S.w, m = S2.x, a = S2.y;
    vec2 A = S.yz;
    float pitch = line_geo.z * sc;
    float L = m * pitch, u, v;
    if (w < 0.03) {
        u = (p.x - A.x) / pitch + 0.5 * m; v = p.y - A.y;
    } else {
        float R = L / (2.0 * PI * w);
        vec2 d = p - (A - vec2(0.0, R));
        float phi = atan(d.x, d.y);                         // clockwise from the top
        if (abs(phi) > PI * w + 1e-3) return vec3(0.0);
        u = phi * R / pitch + 0.5 * m; v = length(d) - R;
    }
    if (u < 0.0 || u >= m) return vec3(0.0);
    float k = floor(u);
    vec2 q = vec2(abs(fract(u) - 0.5) * pitch, abs(v));
    vec2 hs = vec2(0.5 * pitch, 0.5 * pitch * cell_aspect);
    float aa = px();
    float hole = smoothstep(0.0, aa, min(hs.x * 0.66 - q.x, hs.y * 0.80 - q.y));
    float plate = smoothstep(0.0, aa, min(hs.x * 0.92 - q.x, hs.y * 0.96 - q.y)) - hole;
    float closed = step(m - 1.5, k);
    vec3 c = DEEP * 0.7 * plate + hole * mix(TEAL * 0.55, DARK * 0.25, closed);
    return c * a;
}

vec3 sieve_machine(vec2 p, vec3 c) {
    // strips
    for (int i = 0; i < 8; i++) {
        if (i >= n_strip) break;
        c += strip_col(p, strip[i], strip2[i]);
    }
    float fl = 1.0 + 1.5 * land_flash;
    // the lamp
    vec2 LP = vec2(lamp_x, beam_y);
    c += (WHITE * 0.7 + CYAN * 0.4) * lamp_on * (smoothstep(0.024, 0.018, length(p - LP)) + 0.4 * glow(length(p - LP), 0.03));
    // the beam, left to right through the wheels in their slots
    float xprev = lamp_x;
    vec3 b = vec3(0.0);
    for (int k = 0; k < 8; k++) {
        if (k >= n_whl) break;
        b += beam(p, vec2(xprev, beam_y), vec2(whl[k].x, beam_y), beam_I[k] * fl, 1.6 * px());
        xprev = whl[k].x;
    }
    b += beam(p, vec2(xprev, beam_y), vec2(cell_x, beam_y), beam_I[n_whl] * fl, 1.8 * px());
    c += b;
    // the wheels over it: light only shows through their holes
    for (int k = 0; k < 8; k++) {
        if (k >= n_whl) break;
        if (whl[k].w <= 0.0) continue;
        vec4 w = wheel(p, whl[k].xy, whl[k].z, whl2[k].x, whl2[k].y, 0.0, 0.0, whl2[k].z, whl2[k].w * fl, whl[k].w);
        c = c * (1.0 - w.a) + w.rgb;
        c += station_col(float(k)) * 0.9 * whl[k].w * gnum(whl2[k].x, p, whl[k].xy - vec2(0.0, 0.40 * whl[k].z), 0.30 * whl[k].z);
    }
    // the photocell: lights with the light that reaches it; the candidate it saw above it
    vec2 CP = vec2(cell_x, beam_y);
    vec2 q = abs(p - CP);
    float on = 0.0;                                         // the cell comes with the first wheel
    for (int k = 0; k < 8; k++) if (k < n_whl) on = max(on, whl[k].w);
    float box = step(q.x, 0.018) * step(q.y, 0.045) * on;
    float I = beam_I[n_whl];
    c += box * (DEEP * 0.9 + (GREEN * 1.3 + WHITE * 0.5) * I * fl);
    c += GREEN * 0.5 * I * fl * glow(length(p - CP), 0.05) * lamp_on;
    c += mix(CYAN * 0.5, GREEN * 1.3, I) * cand_a * gnum(cand, p, CP + vec2(0.0, 0.11), 0.035);
    return c;
}
