/*
 * Luminos Live Wallpaper — Geometric Grid
 * GLSL ES 2.0 fragment shader
 *
 * Regular grid of dots that grow near cursor,
 * ripple wave on keypress, breathing pulse when idle.
 */
precision mediump float;

uniform float u_time;
uniform vec2  u_resolution;
uniform vec2  u_mouse;
uniform float u_mouse_speed;
uniform float u_key_pulse;
uniform float u_intensity;
uniform float u_idle_factor;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    float aspect = u_resolution.x / u_resolution.y;

    /* Background: #0A0A0F */
    vec3 bg = vec3(0.039, 0.039, 0.059);

    /* Accent: #0080FF */
    vec3 accent = vec3(0.0, 0.502, 1.0);

    /* Grid parameters */
    float grid_spacing = 40.0;  /* pixels */
    vec2 grid_size = u_resolution / grid_spacing;

    /* Grid cell coordinates */
    vec2 cell_uv = fract(gl_FragCoord.xy / grid_spacing);
    vec2 cell_id = floor(gl_FragCoord.xy / grid_spacing);

    /* Distance from cell center */
    float d = length(cell_uv - 0.5) * grid_spacing;

    /* Base dot radius: 3px */
    float base_r = 3.0;
    /* Max radius near cursor: 8px */
    float max_r = 8.0;

    /* Mouse position in pixel coords */
    vec2 mouse_px = u_mouse * u_resolution;
    /* Center of this grid cell in pixels */
    vec2 cell_center = (cell_id + 0.5) * grid_spacing;

    /* Distance from cell center to mouse */
    float mouse_dist = length(cell_center - mouse_px);
    float glow_radius = 200.0 * u_intensity;

    /* Proximity glow: dots grow near cursor */
    float proximity = 1.0 - clamp(mouse_dist / glow_radius, 0.0, 1.0);
    proximity = proximity * proximity; /* ease in */
    float dot_r = mix(base_r, max_r, proximity);

    /* Breathing pulse when idle — all dots together */
    float breath = 0.5 + 0.5 * sin(u_time * 0.8);
    float breath_factor = mix(breath, 1.0, u_idle_factor);
    dot_r *= (0.7 + 0.3 * breath_factor);

    /* Key pulse ripple: expanding ring from cursor position */
    float ripple = 0.0;
    if (u_key_pulse > 0.01) {
        /* Ripple expands over time — use key_pulse decay as timer */
        /* key_pulse starts at 1.0, decays to 0 over ~0.5s */
        float ripple_progress = 1.0 - u_key_pulse;
        float ripple_radius = ripple_progress * 600.0 * u_intensity;
        float ripple_width = 80.0;
        float ripple_dist = abs(mouse_dist - ripple_radius);
        ripple = smoothstep(ripple_width, 0.0, ripple_dist) * u_key_pulse;
        dot_r += ripple * 4.0;
    }

    /* Draw the dot */
    float dot = smoothstep(dot_r + 1.0, dot_r - 1.0, d);

    /* Dot brightness: base + proximity glow + ripple */
    float brightness = 0.3 + 0.7 * proximity;
    brightness += ripple * 0.5;
    /* Idle: reduce base brightness */
    brightness *= (0.4 + 0.6 * u_idle_factor);

    /* Compose */
    vec3 col = bg;
    col = mix(col, accent * brightness, dot);

    /* Subtle grid line hint (very faint) */
    float grid_line = 0.0;
    vec2 grid_d = abs(cell_uv - 0.5);
    float line_dist = min(grid_d.x, grid_d.y) * grid_spacing;
    if (line_dist < 0.5) {
        grid_line = (0.5 - line_dist) * 0.04 * u_intensity * u_idle_factor;
    }
    col += accent * grid_line;

    /* Mouse speed: nearby dots pulse brighter */
    col += accent * dot * u_mouse_speed * proximity * 0.3 * u_intensity;

    /* Vignette */
    float vig = 1.0 - 0.25 * length(uv - 0.5);
    col *= vig;

    col = clamp(col, 0.0, 1.0);
    gl_FragColor = vec4(col, 1.0);
}
