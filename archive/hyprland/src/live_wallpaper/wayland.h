#ifndef LUMINOS_WAYLAND_H
#define LUMINOS_WAYLAND_H

#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"

struct LuminosWayland {
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct wl_surface *surface;
    struct wl_output *output;
    struct zwlr_layer_shell_v1 *layer_shell;
    struct zwlr_layer_surface_v1 *layer_surface;
    struct wl_seat *seat;
    struct wl_pointer *pointer;
    struct wl_keyboard *keyboard;
    struct wl_egl_window *egl_window;
    int width, height;
    int configured;
    int running;
    const char *output_name;       /* --output flag, NULL = primary */
    int output_matched;            /* found the requested output */
};

int  wayland_init(struct LuminosWayland *wl);
void wayland_destroy(struct LuminosWayland *wl);
int  wayland_dispatch(struct LuminosWayland *wl);

#endif
