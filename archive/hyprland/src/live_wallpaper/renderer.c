#include "renderer.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ------------------------------------------------------------------ */
/* Embedded shader sources                                            */
/* ------------------------------------------------------------------ */

static const char *vertex_shader_src =
    "attribute vec2 a_position;\n"
    "void main() {\n"
    "    gl_Position = vec4(a_position, 0.0, 1.0);\n"
    "}\n";

/* Fullscreen quad vertices (two triangles) */
static const float quad_vertices[] = {
    -1.0f, -1.0f,
     1.0f, -1.0f,
    -1.0f,  1.0f,
     1.0f, -1.0f,
     1.0f,  1.0f,
    -1.0f,  1.0f,
};

/* ------------------------------------------------------------------ */
/* Shader source loading                                              */
/* ------------------------------------------------------------------ */

static char *load_shader_file(const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f) return NULL;

    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (len <= 0) { fclose(f); return NULL; }

    char *buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); return NULL; }

    size_t nread = fread(buf, 1, (size_t)len, f);
    buf[nread] = '\0';
    fclose(f);
    return buf;
}

static const char *find_preset_path(const char *preset, char *buf, size_t buflen)
{
    /* Search order: ./presets/, install path */
    const char *dirs[] = {
        "presets",
        "/usr/share/luminos/live-wallpaper/presets",
        "/usr/local/share/luminos/live-wallpaper/presets",
        NULL
    };

    for (int i = 0; dirs[i]; i++) {
        snprintf(buf, buflen, "%s/%s.glsl", dirs[i], preset);
        FILE *f = fopen(buf, "r");
        if (f) { fclose(f); return buf; }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Embedded fallback presets (minimal versions)                       */
/* ------------------------------------------------------------------ */

/* particles.glsl — embedded fallback */
static const char *particles_frag_src =
    "precision mediump float;\n"
    "uniform float u_time;\n"
    "uniform vec2 u_resolution;\n"
    "uniform vec2 u_mouse;\n"
    "uniform float u_mouse_speed;\n"
    "uniform float u_key_pulse;\n"
    "uniform float u_intensity;\n"
    "uniform float u_idle_factor;\n"
    "float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}\n"
    "vec2 hash2(vec2 p){return fract(sin(vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3))))*43758.5453);}\n"
    "void main(){\n"
    "  vec2 uv=gl_FragCoord.xy/u_resolution;\n"
    "  float aspect=u_resolution.x/u_resolution.y;\n"
    "  vec3 bg=vec3(0.039,0.039,0.059);\n"
    "  vec3 accent=vec3(0.0,0.502,1.0);\n"
    "  vec2 pos=vec2(uv.x*aspect,uv.y);\n"
    "  vec2 mouse=vec2(u_mouse.x*aspect,u_mouse.y);\n"
    "  float t=u_time;\n"
    "  float acc=0.0;\n"
    "  for(float gy=0.0;gy<12.0;gy+=1.0){\n"
    "    for(float gx=0.0;gx<12.0;gx+=1.0){\n"
    "      vec2 cell=vec2(gx,gy);\n"
    "      vec2 rnd=hash2(cell);\n"
    "      vec2 sp=vec2((cell.x+rnd.x+sin(t*0.15*u_idle_factor+rnd.x*6.28)*0.3)/12.0*aspect,"
    "                    (cell.y+rnd.y+cos(t*0.1*u_idle_factor+rnd.y*6.28)*0.3)/12.0);\n"
    "      vec2 tm=sp-mouse;\n"
    "      float md=length(tm);\n"
    "      if(md<0.15*u_intensity&&md>0.001)sp+=normalize(tm)*(1.0-md/(0.15*u_intensity))*(1.0-md/(0.15*u_intensity))*0.08;\n"
    "      float d=length(pos-sp);\n"
    "      float glow=(3.0/u_resolution.y)/(d+0.001);\n"
    "      acc+=smoothstep(0.0,1.0,glow-0.5)*0.7*u_intensity;\n"
    "    }\n"
    "  }\n"
    "  vec3 col=bg+accent*acc+accent*u_key_pulse*0.3*u_intensity;\n"
    "  col*=1.0-0.3*length(uv-0.5);\n"
    "  gl_FragColor=vec4(clamp(col,0.0,1.0),1.0);\n"
    "}\n";

/* aurora.glsl — embedded fallback */
static const char *aurora_frag_src =
    "precision mediump float;\n"
    "uniform float u_time;\n"
    "uniform vec2 u_resolution;\n"
    "uniform vec2 u_mouse;\n"
    "uniform float u_mouse_speed;\n"
    "uniform float u_key_pulse;\n"
    "uniform float u_intensity;\n"
    "uniform float u_idle_factor;\n"
    "float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}\n"
    "float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);\n"
    "  return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}\n"
    "float fbm(vec2 p){float v=0.0;float a=0.5;for(int i=0;i<5;i++){v+=a*noise(p);a*=0.5;p*=2.0;}return v;}\n"
    "void main(){\n"
    "  vec2 uv=gl_FragCoord.xy/u_resolution;\n"
    "  vec3 bg=vec3(0.039,0.086,0.157);\n"
    "  float t=u_time*0.15*u_idle_factor;\n"
    "  float hue_shift=(u_mouse.x-0.5)*0.083*u_intensity;\n"
    "  float amp_mod=1.0+(u_mouse.y-0.5)*0.5*u_intensity;\n"
    "  vec3 col=bg;\n"
    "  for(int band=0;band<4;band++){\n"
    "    float fb=float(band);\n"
    "    float center=0.35+fb*0.12+sin(t*0.3+fb*1.5)*0.04*amp_mod;\n"
    "    float wave=(fbm(vec2(uv.x*3.0+t+fb*2.0,fb*10.0))-0.5)*0.15*amp_mod*u_intensity;\n"
    "    float d=abs(uv.y-center-wave);\n"
    "    float bw=0.06+0.02*sin(t+fb*2.5);\n"
    "    float bv=smoothstep(bw,0.0,d)*(0.5+0.5*fbm(vec2(uv.x*5.0+t*0.5,uv.y*2.0+fb)));\n"
    "    vec3 midtone=vec3(0.0,0.502,1.0);\n"
    "    vec3 highlight=vec3(0.482,0.184,1.0);\n"
    "    vec3 bc=mix(midtone,highlight,fb/3.0+hue_shift);\n"
    "    col=mix(col,bc,bv*u_intensity);\n"
    "  }\n"
    "  col+=vec3(0.0,0.502,1.0)*u_key_pulse*0.15;\n"
    "  col*=(0.7+0.3*uv.y)*(1.0-0.4*length(uv-0.5));\n"
    "  gl_FragColor=vec4(clamp(col,0.0,1.0),1.0);\n"
    "}\n";

/* geometric.glsl — embedded fallback */
static const char *geometric_frag_src =
    "precision mediump float;\n"
    "uniform float u_time;\n"
    "uniform vec2 u_resolution;\n"
    "uniform vec2 u_mouse;\n"
    "uniform float u_mouse_speed;\n"
    "uniform float u_key_pulse;\n"
    "uniform float u_intensity;\n"
    "uniform float u_idle_factor;\n"
    "void main(){\n"
    "  vec2 uv=gl_FragCoord.xy/u_resolution;\n"
    "  vec3 bg=vec3(0.039,0.039,0.059);\n"
    "  vec3 accent=vec3(0.0,0.502,1.0);\n"
    "  float gs=40.0;\n"
    "  vec2 cell_uv=fract(gl_FragCoord.xy/gs);\n"
    "  vec2 cell_id=floor(gl_FragCoord.xy/gs);\n"
    "  float d=length(cell_uv-0.5)*gs;\n"
    "  vec2 mouse_px=u_mouse*u_resolution;\n"
    "  vec2 cc=(cell_id+0.5)*gs;\n"
    "  float md=length(cc-mouse_px);\n"
    "  float prox=1.0-clamp(md/(200.0*u_intensity),0.0,1.0);\n"
    "  prox*=prox;\n"
    "  float dot_r=mix(3.0,8.0,prox);\n"
    "  float breath=0.5+0.5*sin(u_time*0.8);\n"
    "  dot_r*=(0.7+0.3*mix(breath,1.0,u_idle_factor));\n"
    "  float ripple=0.0;\n"
    "  if(u_key_pulse>0.01){\n"
    "    float rr=(1.0-u_key_pulse)*600.0*u_intensity;\n"
    "    ripple=smoothstep(80.0,0.0,abs(md-rr))*u_key_pulse;\n"
    "    dot_r+=ripple*4.0;\n"
    "  }\n"
    "  float dot_v=smoothstep(dot_r+1.0,dot_r-1.0,d);\n"
    "  float bright=0.3+0.7*prox+ripple*0.5;\n"
    "  bright*=(0.4+0.6*u_idle_factor);\n"
    "  vec3 col=mix(bg,accent*bright,dot_v);\n"
    "  col*=1.0-0.25*length(uv-0.5);\n"
    "  gl_FragColor=vec4(clamp(col,0.0,1.0),1.0);\n"
    "}\n";

static const char *get_embedded_preset(const char *name)
{
    if (strcmp(name, "particles") == 0)  return particles_frag_src;
    if (strcmp(name, "aurora") == 0)     return aurora_frag_src;
    if (strcmp(name, "geometric") == 0)  return geometric_frag_src;
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Shader compilation                                                 */
/* ------------------------------------------------------------------ */

static GLuint compile_shader(GLenum type, const char *src)
{
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &src, NULL);
    glCompileShader(shader);

    GLint ok;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetShaderInfoLog(shader, sizeof(log), NULL, log);
        fprintf(stderr, "[luminos-wallpaper] shader compile error:\n%s\n", log);
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

static GLuint link_program(GLuint vs, GLuint fs)
{
    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    glBindAttribLocation(prog, 0, "a_position");
    glLinkProgram(prog);

    GLint ok;
    glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(prog, sizeof(log), NULL, log);
        fprintf(stderr, "[luminos-wallpaper] program link error:\n%s\n", log);
        glDeleteProgram(prog);
        return 0;
    }
    return prog;
}

/* ------------------------------------------------------------------ */
/* Time utility                                                       */
/* ------------------------------------------------------------------ */

double renderer_get_time(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */

int renderer_init(struct LuminosRenderer *r, const char *preset,
                  float intensity, int width, int height)
{
    memset(r, 0, sizeof(*r));
    r->intensity   = intensity;
    r->idle_factor = 1.0f;
    r->width       = width;
    r->height      = height;
    r->start_time  = renderer_get_time();
    r->last_input_time = r->start_time;
    strncpy(r->current_preset, preset, sizeof(r->current_preset) - 1);

    /* Create fullscreen quad VBO */
    glGenBuffers(1, &r->vbo);
    glBindBuffer(GL_ARRAY_BUFFER, r->vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(quad_vertices),
                 quad_vertices, GL_STATIC_DRAW);

    /* Load and compile shaders */
    if (renderer_load_preset(r, preset) < 0)
        return -1;

    return 0;
}

int renderer_load_preset(struct LuminosRenderer *r, const char *preset)
{
    /* Clean up old program */
    if (r->program) {
        glDeleteProgram(r->program);
        r->program = 0;
    }

    /* Try loading from file first, fall back to embedded */
    char path_buf[512];
    const char *frag_src = NULL;
    char *file_src = NULL;

    const char *path = find_preset_path(preset, path_buf, sizeof(path_buf));
    if (path) {
        file_src = load_shader_file(path);
        if (file_src) {
            frag_src = file_src;
            fprintf(stderr, "[luminos-wallpaper] loaded preset: %s\n", path);
        }
    }

    if (!frag_src) {
        frag_src = get_embedded_preset(preset);
        if (frag_src) {
            fprintf(stderr, "[luminos-wallpaper] using embedded preset: %s\n",
                    preset);
        }
    }

    if (!frag_src) {
        fprintf(stderr, "[luminos-wallpaper] unknown preset: %s\n", preset);
        free(file_src);
        return -1;
    }

    /* Compile */
    GLuint vs = compile_shader(GL_VERTEX_SHADER, vertex_shader_src);
    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, frag_src);
    free(file_src);

    if (!vs || !fs) {
        if (vs) glDeleteShader(vs);
        if (fs) glDeleteShader(fs);
        return -1;
    }

    r->program = link_program(vs, fs);
    glDeleteShader(vs);
    glDeleteShader(fs);

    if (!r->program)
        return -1;

    /* Cache uniform locations */
    r->loc_time        = glGetUniformLocation(r->program, "u_time");
    r->loc_resolution  = glGetUniformLocation(r->program, "u_resolution");
    r->loc_mouse       = glGetUniformLocation(r->program, "u_mouse");
    r->loc_mouse_speed = glGetUniformLocation(r->program, "u_mouse_speed");
    r->loc_key_pulse   = glGetUniformLocation(r->program, "u_key_pulse");
    r->loc_intensity   = glGetUniformLocation(r->program, "u_intensity");
    r->loc_idle_factor = glGetUniformLocation(r->program, "u_idle_factor");

    strncpy(r->current_preset, preset, sizeof(r->current_preset) - 1);
    return 0;
}

void renderer_frame(struct LuminosRenderer *r)
{
    if (r->suspended || r->paused || !r->program)
        return;

    double now = renderer_get_time();
    float elapsed = (float)(now - r->start_time);

    /* Idle detection */
    double idle_seconds = now - r->last_input_time;
    if (idle_seconds > 120.0) {
        /* 2+ minutes idle: decay to 0.1 */
        float target = 0.1f;
        r->idle_factor += (target - r->idle_factor) * 0.01f;
    } else if (idle_seconds > 30.0) {
        /* 30s+ idle: decay to 0.3 */
        float target = 0.3f;
        r->idle_factor += (target - r->idle_factor) * 0.02f;
    }

    /* Key pulse decay: exponential, 0.92 per frame at 60fps */
    r->key_pulse *= 0.92f;
    if (r->key_pulse < 0.001f)
        r->key_pulse = 0.0f;

    /* Mouse speed decay */
    r->mouse_speed *= 0.95f;
    if (r->mouse_speed < 0.001f)
        r->mouse_speed = 0.0f;

    /* Render */
    glViewport(0, 0, r->width, r->height);
    glClear(GL_COLOR_BUFFER_BIT);

    glUseProgram(r->program);

    glUniform1f(r->loc_time, elapsed);
    glUniform2f(r->loc_resolution, (float)r->width, (float)r->height);
    glUniform2f(r->loc_mouse, r->mouse_x, r->mouse_y);
    glUniform1f(r->loc_mouse_speed, r->mouse_speed);
    glUniform1f(r->loc_key_pulse, r->key_pulse);
    glUniform1f(r->loc_intensity, r->intensity);
    glUniform1f(r->loc_idle_factor, r->idle_factor);

    glBindBuffer(GL_ARRAY_BUFFER, r->vbo);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);

    glDrawArrays(GL_TRIANGLES, 0, 6);

    glDisableVertexAttribArray(0);
}

void renderer_set_mouse(struct LuminosRenderer *r, float x, float y)
{
    /* Calculate speed from delta */
    float dx = x - r->prev_mouse_x;
    float dy = y - r->prev_mouse_y;
    float delta = sqrtf(dx * dx + dy * dy);

    r->mouse_speed = delta * 10.0f; /* scale up for visibility */
    if (r->mouse_speed > 1.0f) r->mouse_speed = 1.0f;

    r->prev_mouse_x = r->mouse_x;
    r->prev_mouse_y = r->mouse_y;
    r->mouse_x = x;
    r->mouse_y = y;

    r->last_input_time = renderer_get_time();
    r->idle_factor = 1.0f;
}

void renderer_on_key(struct LuminosRenderer *r)
{
    r->key_pulse = 1.0f;
    r->last_input_time = renderer_get_time();
    r->idle_factor = 1.0f;
}

void renderer_set_intensity(struct LuminosRenderer *r, float intensity)
{
    r->intensity = intensity;
}

void renderer_set_size(struct LuminosRenderer *r, int width, int height)
{
    r->width  = width;
    r->height = height;
}

void renderer_suspend(struct LuminosRenderer *r)
{
    r->suspended = 1;
    fprintf(stderr, "[luminos-wallpaper] rendering suspended\n");
}

void renderer_resume(struct LuminosRenderer *r)
{
    r->suspended = 0;
    r->paused = 0;
    fprintf(stderr, "[luminos-wallpaper] rendering resumed\n");
}

void renderer_pause(struct LuminosRenderer *r)
{
    r->paused = 1;
    fprintf(stderr, "[luminos-wallpaper] rendering paused\n");
}

void renderer_destroy(struct LuminosRenderer *r)
{
    if (r->program)
        glDeleteProgram(r->program);
    if (r->vbo)
        glDeleteBuffers(1, &r->vbo);
}
