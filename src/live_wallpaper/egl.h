#ifndef LUMINOS_EGL_H
#define LUMINOS_EGL_H

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include "wayland.h"

struct LuminosEGL {
    EGLDisplay display;
    EGLContext context;
    EGLSurface surface;
    EGLConfig  config;
    char device_path[256];   /* path to the AMD DRM device */
};

int  egl_init(struct LuminosEGL *egl, struct LuminosWayland *wl);
void egl_swap(struct LuminosEGL *egl);
void egl_destroy(struct LuminosEGL *egl);

/* Returns path to AMD GPU device e.g. /dev/dri/renderD128 */
const char *egl_find_amd_device(void);

#endif
