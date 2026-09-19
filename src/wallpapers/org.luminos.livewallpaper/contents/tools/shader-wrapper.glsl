#version 440
// The Qt 6 shell a Shadertoy shader is wrapped in.  SPEC §3.4, DECISION 119.
// [CHANGE: claude-code | 2026-09-19]  SPDX-License-Identifier: GPL-3.0-or-later
//
// Data, not code: it lives beside luminos-shader-bake so it can be read and
// edited as GLSL instead of as a Python string. The percent-props placeholder
// below is where the uniforms generated from properties.json are spliced in, and
// the EPILOGUE-SPLIT marker divides what goes BEFORE the user's source from what
// goes after. Do NOT write that placeholder anywhere else in this file, comments
// included -- the whole file goes through one percent-format and a placeholder
// inside a comment splices declarations into it and breaks the next line.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 luminos_fragColor;
layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    float iTime;
    vec2  iResolutionXY;
    vec4  iMouse;
    float iBass;
    float iMid;
    float iTreble;
    float iAudioActive;
%(props)s};
// CONTRACTS §2: the 128x1 spectrum, in Shadertoy's iChannel0 slot.
layout(binding = 1) uniform sampler2D iChannel0;
#define iResolution vec3(iResolutionXY, 1.0)
#define iChannel1 iChannel0
#define iChannel2 iChannel0
#define iChannel3 iChannel0
#define texture2D texture
//EPILOGUE-SPLIT
void main() {
    // Shadertoy's origin is bottom-left; Qt's texcoord is top-left.
    vec2 fragCoord = vec2(qt_TexCoord0.x, 1.0 - qt_TexCoord0.y) * iResolutionXY;
    vec4 luminos_c = vec4(0.0, 0.0, 0.0, 1.0);
    mainImage(luminos_c, fragCoord);
    luminos_fragColor = vec4(luminos_c.rgb, 1.0) * qt_Opacity;
}
