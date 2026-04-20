#include "egl.h"

#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <xf86drm.h>

/* ------------------------------------------------------------------ */
/* AMD iGPU device detection via libdrm                               */
/* ------------------------------------------------------------------ */

static char amd_device_path[256];

const char *egl_find_amd_device(void)
{
    DIR *dir = opendir("/dev/dri");
    if (!dir)
        return NULL;

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        /* Check render nodes first (renderD128, renderD129, ...) */
        if (strncmp(entry->d_name, "renderD", 7) != 0)
            continue;

        char path[256];
        snprintf(path, sizeof(path), "/dev/dri/%s", entry->d_name);

        int fd = open(path, O_RDWR);
        if (fd < 0)
            continue;

        drmVersionPtr ver = drmGetVersion(fd);
        if (ver) {
            if (strcmp(ver->name, "amdgpu") == 0 ||
                strcmp(ver->name, "radeon") == 0) {
                strncpy(amd_device_path, path, sizeof(amd_device_path) - 1);
                amd_device_path[sizeof(amd_device_path) - 1] = '\0';
                drmFreeVersion(ver);
                close(fd);
                closedir(dir);
                fprintf(stderr, "[luminos-wallpaper] AMD iGPU: %s (%s)\n",
                        amd_device_path, ver->name);
                return amd_device_path;
            }
            /* Print version name before freeing for debugging */
            drmFreeVersion(ver);
        }
        close(fd);
    }
    closedir(dir);

    /* Also check card nodes as fallback */
    dir = opendir("/dev/dri");
    if (!dir)
        return NULL;

    while ((entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "card", 4) != 0)
            continue;

        char path[256];
        snprintf(path, sizeof(path), "/dev/dri/%s", entry->d_name);

        int fd = open(path, O_RDWR);
        if (fd < 0)
            continue;

        drmVersionPtr ver = drmGetVersion(fd);
        if (ver) {
            if (strcmp(ver->name, "amdgpu") == 0 ||
                strcmp(ver->name, "radeon") == 0) {
                strncpy(amd_device_path, path, sizeof(amd_device_path) - 1);
                amd_device_path[sizeof(amd_device_path) - 1] = '\0';
                fprintf(stderr, "[luminos-wallpaper] AMD iGPU: %s (%s)\n",
                        amd_device_path, ver->name);
                drmFreeVersion(ver);
                close(fd);
                closedir(dir);
                return amd_device_path;
            }
            drmFreeVersion(ver);
        }
        close(fd);
    }
    closedir(dir);
    return NULL;
}

/* ------------------------------------------------------------------ */
/* EGL initialization                                                 */
/* ------------------------------------------------------------------ */

int egl_init(struct LuminosEGL *egl, struct LuminosWayland *wl)
{
    memset(egl, 0, sizeof(*egl));

    /* Find AMD device and force Mesa to use it */
    const char *amd_dev = egl_find_amd_device();
    if (amd_dev) {
        strncpy(egl->device_path, amd_dev, sizeof(egl->device_path) - 1);
        /*
         * DRI_PRIME selects the GPU for Mesa's Wayland EGL.
         * On hybrid AMD+NVIDIA, AMD iGPU is usually device 0.
         * Setting the render node path forces the right device.
         */
        setenv("DRI_PRIME", amd_dev, 1);
        fprintf(stderr, "[luminos-wallpaper] forcing GPU via DRI_PRIME=%s\n",
                amd_dev);
    } else {
        fprintf(stderr, "[luminos-wallpaper] WARNING: no AMD GPU found, "
                        "using default device\n");
    }

    /* Get EGL display from Wayland display */
    egl->display = eglGetDisplay((EGLNativeDisplayType)wl->display);
    if (egl->display == EGL_NO_DISPLAY) {
        fprintf(stderr, "[luminos-wallpaper] eglGetDisplay failed\n");
        return -1;
    }

    EGLint major, minor;
    if (!eglInitialize(egl->display, &major, &minor)) {
        fprintf(stderr, "[luminos-wallpaper] eglInitialize failed\n");
        return -1;
    }
    fprintf(stderr, "[luminos-wallpaper] EGL %d.%d initialized\n",
            major, minor);

    /* Verify we're using Mesa/AMD, not NVIDIA proprietary */
    const char *vendor = eglQueryString(egl->display, EGL_VENDOR);
    const char *apis   = eglQueryString(egl->display, EGL_CLIENT_APIS);
    fprintf(stderr, "[luminos-wallpaper] EGL vendor: %s\n",
            vendor ? vendor : "unknown");
    fprintf(stderr, "[luminos-wallpaper] EGL APIs: %s\n",
            apis ? apis : "unknown");

    if (!eglBindAPI(EGL_OPENGL_ES_API)) {
        fprintf(stderr, "[luminos-wallpaper] eglBindAPI(GLES) failed\n");
        return -1;
    }

    /* Choose config with RGBA8888 */
    EGLint config_attribs[] = {
        EGL_SURFACE_TYPE,    EGL_WINDOW_BIT,
        EGL_RED_SIZE,        8,
        EGL_GREEN_SIZE,      8,
        EGL_BLUE_SIZE,       8,
        EGL_ALPHA_SIZE,      8,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_NONE
    };

    EGLint num_configs;
    if (!eglChooseConfig(egl->display, config_attribs,
                         &egl->config, 1, &num_configs) ||
        num_configs == 0) {
        fprintf(stderr, "[luminos-wallpaper] eglChooseConfig failed\n");
        return -1;
    }

    /* Create OpenGL ES 2.0 context */
    EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 2,
        EGL_NONE
    };

    egl->context = eglCreateContext(egl->display, egl->config,
                                    EGL_NO_CONTEXT, context_attribs);
    if (egl->context == EGL_NO_CONTEXT) {
        fprintf(stderr, "[luminos-wallpaper] eglCreateContext failed\n");
        return -1;
    }

    /* Create EGL window surface from Wayland EGL window */
    if (!wl->egl_window) {
        fprintf(stderr, "[luminos-wallpaper] no wl_egl_window\n");
        return -1;
    }

    egl->surface = eglCreateWindowSurface(egl->display, egl->config,
                                          (EGLNativeWindowType)wl->egl_window,
                                          NULL);
    if (egl->surface == EGL_NO_SURFACE) {
        fprintf(stderr, "[luminos-wallpaper] eglCreateWindowSurface failed\n");
        return -1;
    }

    if (!eglMakeCurrent(egl->display, egl->surface,
                        egl->surface, egl->context)) {
        fprintf(stderr, "[luminos-wallpaper] eglMakeCurrent failed\n");
        return -1;
    }

    /* Log GL renderer to confirm we're on AMD */
    const char *gl_renderer = (const char *)glGetString(GL_RENDERER);
    const char *gl_vendor   = (const char *)glGetString(GL_VENDOR);
    fprintf(stderr, "[luminos-wallpaper] GL renderer: %s\n",
            gl_renderer ? gl_renderer : "unknown");
    fprintf(stderr, "[luminos-wallpaper] GL vendor: %s\n",
            gl_vendor ? gl_vendor : "unknown");

    if (gl_renderer && (strstr(gl_renderer, "NVIDIA") ||
                        strstr(gl_renderer, "nvidia"))) {
        fprintf(stderr, "[luminos-wallpaper] WARNING: running on NVIDIA! "
                        "Expected AMD iGPU. Check DRI_PRIME.\n");
    }

    /* Disable vsync — we do our own frame timing */
    eglSwapInterval(egl->display, 0);

    return 0;
}

void egl_swap(struct LuminosEGL *egl)
{
    eglSwapBuffers(egl->display, egl->surface);
}

void egl_destroy(struct LuminosEGL *egl)
{
    if (egl->display != EGL_NO_DISPLAY) {
        eglMakeCurrent(egl->display, EGL_NO_SURFACE,
                        EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (egl->surface != EGL_NO_SURFACE)
            eglDestroySurface(egl->display, egl->surface);
        if (egl->context != EGL_NO_CONTEXT)
            eglDestroyContext(egl->display, egl->context);
        eglTerminate(egl->display);
    }
}
