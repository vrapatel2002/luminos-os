/*
 * Luminos Live Wallpaper — Aurora
 * GLSL ES 2.0 fragment shader
 *
 * Flowing horizontal light bands — northern lights style.
 * Mouse X shifts hue, mouse Y changes amplitude.
 * Keypress triggers brightness surge.
 */
precision mediump float;

uniform float u_time;
uniform vec2  u_resolution;
uniform vec2  u_mouse;
uniform float u_mouse_speed;
uniform float u_key_pulse;
uniform float u_intensity;
uniform float u_idle_factor;

/* --- Noise functions --- */

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f); /* smoothstep */

    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

/* Fractal Brownian Motion — 5 octaves */
float fbm(vec2 p) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < 5; i++) {
        val += amp * noise(p * freq);
        amp *= 0.5;
        freq *= 2.0;
    }
    return val;
}

/* --- HSV to RGB --- */

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;

    /* Base color: deep dark blue #0A1628 */
    vec3 bg = vec3(0.039, 0.086, 0.157);

    /* Time, slowed by idle factor */
    float t = u_time * 0.15 * u_idle_factor;

    /* Mouse influence */
    float hue_shift = (u_mouse.x - 0.5) * 0.083 * u_intensity; /* ±30 deg = ±0.083 in 0-1 hue */
    float amp_mod = 1.0 + (u_mouse.y - 0.5) * 0.5 * u_intensity;

    /* Aurora bands — 4 layers at different heights */
    float aurora = 0.0;
    vec3 aurora_color = vec3(0.0);

    for (int band = 0; band < 4; band++) {
        float fb = float(band);

        /* Band center height */
        float center = 0.35 + fb * 0.12;
        /* Vertical drift */
        center += sin(t * 0.3 + fb * 1.5) * 0.04 * amp_mod;

        /* Horizontal wave using fbm */
        float wave = fbm(vec2(uv.x * 3.0 + t + fb * 2.0, fb * 10.0));
        wave = (wave - 0.5) * 0.15 * amp_mod * u_intensity;

        /* Distance from fragment to band center */
        float d = abs(uv.y - center - wave);

        /* Soft falloff */
        float band_width = 0.06 + 0.02 * sin(t + fb * 2.5);
        float band_val = smoothstep(band_width, 0.0, d);

        /* Add noise variation to band brightness */
        float n = fbm(vec2(uv.x * 5.0 + t * 0.5, uv.y * 2.0 + fb));
        band_val *= 0.5 + 0.5 * n;

        /* Color per band — blues to purples */
        float base_hue = 0.6 + fb * 0.05 + hue_shift; /* blue region */
        float sat = 0.7 + 0.2 * sin(t + fb);
        float val = 0.8 * u_intensity;
        vec3 bc = hsv2rgb(vec3(fract(base_hue), sat, val));

        /* Mix colors:
           #0080FF (hue ~0.58) for midtone
           #7B2FFF (hue ~0.72) for highlight */
        vec3 midtone  = vec3(0.0, 0.502, 1.0);
        vec3 highlight = vec3(0.482, 0.184, 1.0);
        bc = mix(midtone, highlight, fb / 3.0 + hue_shift);

        aurora += band_val;
        aurora_color += bc * band_val;
    }

    /* Compose */
    vec3 col = bg;
    col = mix(col, aurora_color, clamp(aurora, 0.0, 1.0));

    /* Key pulse: brightness surge across all bands */
    col += aurora_color * u_key_pulse * 0.5;
    /* Also add a subtle global flash */
    col += vec3(0.0, 0.502, 1.0) * u_key_pulse * 0.1;

    /* Mouse speed: subtle energy ripple */
    float energy = u_mouse_speed * 0.15 * u_intensity;
    col += aurora_color * energy;

    /* Slight vertical gradient — darker at bottom */
    col *= 0.7 + 0.3 * uv.y;

    /* Vignette */
    float vig = 1.0 - 0.4 * length(uv - vec2(0.5, 0.5));
    col *= vig;

    col = clamp(col, 0.0, 1.0);
    gl_FragColor = vec4(col, 1.0);
}
