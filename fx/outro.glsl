// Outro, sung (render.py uniforms_outro): "The survivors of a sieve / are the places where the
// light gets through." type out word by word on the sung words (3:33-3:47) and hold through
// the full-band tail. The line's survivors glow underneath. A clock fades in as the voice
// ends; its hand steps once per beat of the tail and stops on the last beat (3:58.47); black
// from the hard stop.
uniform float len0, len1, shown0, shown1, t_l0, t_l1, typing;
uniform float n_step, since_step, steps_total, stopped, black, clock_a;

const vec2 CK = vec2(0.0, 0.42);
const float CR = 0.24;

void main() {
    if (black > 0.5) { frag = vec4(0.0, 0.0, 0.0, 1.0); return; }
    vec2 p = P();
    vec3 c = line_col(p, CYAN);
    // the clock
    if (clock_a > 0.0) {
        float r = length(p - CK);
        vec3 k = DARK * 0.8 * exp(-pow((r - CR) / (1.3 * px()), 2.0));
        float a = atan(p.x - CK.x, p.y - CK.y);
        float notch = abs(fract(a / (2.0 * PI) * 60.0 + 0.5) - 0.5) * 2.0 * PI * r / 60.0;
        k += DARK * 0.7 * step(CR - 0.03, r) * step(r, CR - 0.012) * exp(-pow(notch / px(), 2.0));
        float ha = n_step * 2.0 * PI / 60.0;
        vec2 tip = CK + (CR - 0.04) * vec2(sin(ha), cos(ha));
        float h;
        k += (WHITE * 0.6 + CYAN * 0.3) * glow(seg(p, CK, tip, h), 1.1 * px());
        k += DARK * 1.2 * smoothstep(0.014, 0.010, r);
        if (stopped < 0.5) k += CYAN * 1.2 * exp(-since_step / 0.10) * exp(-pow(length(p - tip) / (3.0 * px()), 2.0));
        c += k * clock_a;
    }
    // the typed lines, a cursor after the last character
    float y0 = -0.18, y1 = -0.32, hh = 0.042;
    c += (WHITE * 0.85 + CYAN * 0.15) * atext(t_l0, p, vec2(0.0, y0), hh, shown0);
    c += (WHITE * 0.85 + GREEN * 0.15) * atext(t_l1, p, vec2(0.0, y1), hh, shown1);
    bool two = shown1 > 0.0;
    float ti = two ? t_l1 : t_l0, sh = two ? shown1 : shown0, cy = two ? y1 : y0;
    float cw = 2.0 * AADV / ACH * hh;                  // one character, P units
    float cx = atext_x(ti, vec2(0.0, cy), hh, sh) + 0.5 * cw;
    float blink = typing > 0.5 ? step(0.5, fract(t * 2.0)) : 1.0;
    if ((shown0 > 0.0 || two) && abs(p.x - cx) < 0.12 * cw && abs(p.y - cy) < 0.6 * hh) c += WHITE * 0.5 * blink;
    frag = vec4(c, 1.0);
}
