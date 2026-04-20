#ifndef LUMINOS_RENDERER_H
#define LUMINOS_RENDERER_H

#include <GLES2/gl2.h>

struct LuminosRenderer {
    GLuint program;
    GLuint vbo;
    GLint loc_time, loc_resolution, loc_mouse;
    GLint loc_mouse_speed, loc_key_pulse;
    GLint loc_intensity, loc_idle_factor;

    float mouse_x, mouse_y;
    float prev_mouse_x, prev_mouse_y;
    float mouse_speed;
    float key_pulse;
    float intensity;        /* 0.3, 0.7, or 1.0 */
    float idle_factor;      /* 1.0 active, decays toward 0.1 */
    double last_input_time;
    double start_time;

    int width, height;
    int suspended;          /* 1 = not rendering (game fullscreen) */
    int paused;             /* 1 = paused (battery mode) */
    char current_preset[64];
};

int  renderer_init(struct LuminosRenderer *r, const char *preset,
                   float intensity, int width, int height);
void renderer_frame(struct LuminosRenderer *r);
void renderer_set_mouse(struct LuminosRenderer *r, float x, float y);
void renderer_on_key(struct LuminosRenderer *r);
void renderer_set_intensity(struct LuminosRenderer *r, float intensity);
void renderer_set_size(struct LuminosRenderer *r, int width, int height);
int  renderer_load_preset(struct LuminosRenderer *r, const char *preset);
void renderer_suspend(struct LuminosRenderer *r);
void renderer_resume(struct LuminosRenderer *r);
void renderer_pause(struct LuminosRenderer *r);
void renderer_destroy(struct LuminosRenderer *r);

double renderer_get_time(void);

#endif
