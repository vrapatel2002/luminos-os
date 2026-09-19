// Luminos sample — a Shadertoy-shaped shader, compiled at runtime, no browser.
// [CHANGE: claude-code | 2026-09-19] SPEC §3.4, DECISION 119
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Nothing here is Luminos-specific: this is ordinary Shadertoy source using
// mainImage/iTime/iResolution/iMouse, plus iChannel0 for the spectrum, which is
// Shadertoy's own audio convention. Paste a shader from the site in place of this
// one and it should run. Every key in luminos-shadertoy.properties.json turns into
// a uniform of the same name AND a control in the wallpaper settings panel.
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    vec2 m  = (iMouse.xy - 0.5 * iResolution.xy) / iResolution.y;

    float t = iTime * uSpeed * 0.2;
    float d = length(uv - m * 0.5);

    // iChannel0 is the 128x1 spectrum: x = frequency, red channel = level.
    float spec = texture(iChannel0, vec2(clamp(abs(uv.x) * 1.4, 0.0, 1.0), 0.5)).r;

    float rings = sin(d * (10.0 + iTreble * 20.0) - t * 6.0) * 0.5 + 0.5;
    vec3 col = mix(vec3(0.04, 0.05, 0.11), uTint.rgb, rings * 0.55);
    col += uTint.rgb * iAudioActive * (iBass * 0.5 + spec * 0.4) * smoothstep(1.0, 0.0, d);
    col += 0.06 * sin(uv.y * 6.0 - t * 3.0);

    fragColor = vec4(col, 1.0);
}
