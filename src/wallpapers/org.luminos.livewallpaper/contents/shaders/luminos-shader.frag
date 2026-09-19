#version 440
// Luminos native shader wallpaper — the WebGL sample from
// contents/samples/luminos-shader.html, ported to a Qt ShaderEffect.
// Same maths, no browser. Compiled to .qsb because Qt 6 dropped inline GLSL.
//
// [CHANGE: claude-code | 2026-09-19] DECISION 117 — audio uniforms + iAudio.
//
// REBUILD after editing (the .qsb next to this file is what actually runs):
//   qsb --glsl "100es,120,150" --hlsl 50 --msl 12 \
//       -o luminos-shader.frag.qsb luminos-shader.frag
// On Arch `qsb` comes from qt6-shadertools, at /usr/lib/qt6/bin/qsb.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;     //   0..63
    float qt_Opacity;    //  64..67
    float iTime;         //  68..71
    vec2  iResolution;   //  72..79   (vec2 needs 8-byte alignment)
    vec2  iMouse;        //  80..87
    float iBass;         //  88..91   0..1, mean of bands[0..15]
    float iMid;          //  92..95   0..1, mean of bands[16..63]
    float iTreble;       //  96..99   0..1, mean of bands[64..127]
    float iAudioActive;  // 100..103  0 when no provider — gates every audio term
};
// CONTRACTS §2: 128x1, red channel = band amplitude, Shadertoy iChannel0 layout.
layout(binding = 1) uniform sampler2D iAudio;

void main() {
    // WebGL's gl_FragCoord is bottom-left, Qt's texcoord is top-left, so y flips.
    vec2 fc = vec2(qt_TexCoord0.x, 1.0 - qt_TexCoord0.y) * iResolution;
    vec2 uv = (fc - 0.5 * iResolution) / iResolution.y;
    vec2 m  = (iMouse - 0.5 * iResolution) / iResolution.y;
    float t = iTime * 0.25;
    float d = length(uv - m * 0.6);
    // Treble tightens the ripple; with no audio this is the original 8.0.
    float w = sin(d * (8.0 + iTreble * 6.0) - iTime * 1.5) * 0.5 + 0.5;
    vec3 a = vec3(0.05, 0.10, 0.25), b = vec3(0.15, 0.55, 0.85), c = vec3(0.85, 0.35, 0.65);
    vec3 col = mix(a, b, 0.5 + 0.5 * sin(uv.x * 2.0 + t));
    col = mix(col, c, w * 0.6);
    col += 0.15 * sin(uv.y * 3.0 - t * 2.0);

    // Audio. Every term is scaled by a value that is 0 with no provider, so the
    // no-audio picture is bit-identical to the pre-audio shader.
    float spec = texture(iAudio, vec2(clamp(qt_TexCoord0.x, 0.0, 1.0), 0.5)).r;
    col += iAudioActive * iBass * 0.30 * vec3(0.55, 0.20, 0.75) * smoothstep(0.9, 0.0, d);
    col += iAudioActive * spec * 0.18 * vec3(0.45, 0.75, 1.00);
    col += iAudioActive * iMid * 0.10;

    fragColor = vec4(col, 1.0) * qt_Opacity;
}
