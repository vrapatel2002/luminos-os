/*
 * Luminos Live Wallpaper — Particle Field
 * GLSL ES 2.0 fragment shader
 *
 * ~200 particles floating, lines between nearby particles,
 * mouse repulsion, keypress burst, idle drift.
 */
precision mediump float;

uniform float u_time;
uniform vec2  u_resolution;
uniform vec2  u_mouse;
uniform float u_mouse_speed;
uniform float u_key_pulse;
uniform float u_intensity;
uniform float u_idle_factor;

/* --- Hash functions for pseudo-random particle positions --- */

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec2 hash2(vec2 p) {
    return fract(sin(vec2(
        dot(p, vec2(127.1, 311.7)),
        dot(p, vec2(269.5, 183.3))
    )) * 43758.5453);
}

/* --- Particle layer --- */

/* Number of particles along each axis — total ~200 */
const float GRID = 15.0;

vec2 particle_pos(vec2 cell, float t) {
    vec2 rnd = hash2(cell);
    /* Base position: random within cell */
    vec2 pos = rnd;
    /* Movement: gentle drift modulated by idle_factor */
    float speed = 0.15 * u_idle_factor * u_intensity;
    pos.x += sin(t * speed + rnd.x * 6.28) * 0.3;
    pos.y += cos(t * speed * 0.7 + rnd.y * 6.28) * 0.3;
    return pos;
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    float aspect = u_resolution.x / u_resolution.y;

    /* Background: #0A0A0F */
    vec3 bg = vec3(0.039, 0.039, 0.059);
    vec3 col = bg;

    /* Accent color: #0080FF */
    vec3 accent = vec3(0.0, 0.502, 1.0);

    /* Screen-space position with aspect correction */
    vec2 pos = vec2(uv.x * aspect, uv.y);
    vec2 mouse = vec2(u_mouse.x * aspect, u_mouse.y);

    float t = u_time;

    /* Key pulse: additive brightness */
    float pulse_glow = u_key_pulse * 0.3 * u_intensity;

    /* Accumulate particle and line contributions */
    float particle_acc = 0.0;
    float line_acc = 0.0;

    /* Connection line threshold in screen space */
    float connect_dist = 150.0 / u_resolution.y;

    /* Store nearby particle positions for line drawing */
    vec2 nearby[4];
    int nearby_count = 0;

    for (float gy = 0.0; gy < GRID; gy += 1.0) {
        for (float gx = 0.0; gx < GRID; gx += 1.0) {
            vec2 cell = vec2(gx, gy);
            vec2 pp = particle_pos(cell, t);

            /* Map particle to screen space */
            vec2 sp = vec2(
                (cell.x + pp.x) / GRID * aspect,
                (cell.y + pp.y) / GRID
            );

            /* Mouse repulsion */
            vec2 to_mouse = sp - mouse;
            float md = length(to_mouse);
            float repulsion_radius = 0.15 * u_intensity;
            if (md < repulsion_radius && md > 0.001) {
                float repel = (1.0 - md / repulsion_radius);
                repel *= repel * 0.08 * (1.0 + u_mouse_speed * 2.0);
                /* Key pulse scatter */
                repel += u_key_pulse * 0.05;
                sp += normalize(to_mouse) * repel;
            }

            /* Distance from this fragment to particle */
            float d = length(pos - sp);

            /* Particle glow */
            float base_size = 3.0 / u_resolution.y;
            float glow = base_size / (d + 0.001);
            glow = smoothstep(0.0, 1.0, glow - 0.5);
            particle_acc += glow * 0.7 * u_intensity;

            /* Collect for connection lines */
            float frag_dist = length(pos - sp);
            if (frag_dist < connect_dist * 2.0 && nearby_count < 4) {
                nearby[nearby_count] = sp;
                nearby_count++;
            }
        }
    }

    /* Draw connection lines between nearby particles */
    /* Sample a subset for performance */
    for (int i = 0; i < 4; i++) {
        if (i >= nearby_count) break;
        for (int j = i + 1; j < 4; j++) {
            if (j >= nearby_count) break;
            float pd = length(nearby[i] - nearby[j]);
            if (pd < connect_dist) {
                /* Distance from fragment to line segment */
                vec2 a = nearby[i];
                vec2 b = nearby[j];
                vec2 pa = pos - a;
                vec2 ba = b - a;
                float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
                float ld = length(pa - ba * h);

                float line_width = 1.5 / u_resolution.y;
                float line = smoothstep(line_width, 0.0, ld);
                line *= (1.0 - pd / connect_dist); /* fade with distance */
                line_acc += line * 0.2 * u_intensity;
            }
        }
    }

    /* Compose */
    col += accent * particle_acc;
    col += accent * line_acc;

    /* Key pulse global brightness boost */
    col += accent * pulse_glow;

    /* Subtle vignette */
    float vig = 1.0 - 0.3 * length(uv - 0.5);
    col *= vig;

    /* Clamp */
    col = clamp(col, 0.0, 1.0);

    gl_FragColor = vec4(col, 1.0);
}
