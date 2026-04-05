#include "wayland.h"
#include "input.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-egl.h>

/* ------------------------------------------------------------------ */
/* Layer surface listener                                             */
/* ------------------------------------------------------------------ */

static void layer_surface_configure(void *data,
                                    struct zwlr_layer_surface_v1 *surface,
                                    uint32_t serial,
                                    uint32_t width, uint32_t height)
{
    struct LuminosWayland *wl = data;

    if (width > 0 && height > 0) {
        wl->width  = (int)width;
        wl->height = (int)height;
    }

    zwlr_layer_surface_v1_ack_configure(surface, serial);

    if (wl->egl_window) {
        wl_egl_window_resize(wl->egl_window, wl->width, wl->height, 0, 0);
    } else {
        wl->egl_window = wl_egl_window_create(wl->surface,
                                               wl->width, wl->height);
    }

    wl->configured = 1;
}

static void layer_surface_closed(void *data,
                                 struct zwlr_layer_surface_v1 *surface)
{
    (void)surface;
    struct LuminosWayland *wl = data;
    wl->running = 0;
}

static const struct zwlr_layer_surface_v1_listener layer_surface_listener = {
    .configure = layer_surface_configure,
    .closed    = layer_surface_closed,
};

/* ------------------------------------------------------------------ */
/* Output listener — match --output flag                              */
/* ------------------------------------------------------------------ */

static void output_geometry(void *data, struct wl_output *output,
                            int32_t x, int32_t y,
                            int32_t pw, int32_t ph,
                            int32_t subpixel,
                            const char *make, const char *model,
                            int32_t transform)
{
    (void)data; (void)output; (void)x; (void)y;
    (void)pw; (void)ph; (void)subpixel;
    (void)make; (void)model; (void)transform;
}

static void output_mode(void *data, struct wl_output *output,
                        uint32_t flags, int32_t width, int32_t height,
                        int32_t refresh)
{
    struct LuminosWayland *wl = data;
    if (flags & WL_OUTPUT_MODE_CURRENT) {
        if (wl->width == 0 && wl->height == 0) {
            wl->width  = width;
            wl->height = height;
        }
    }
    (void)output; (void)refresh;
}

static void output_done(void *data, struct wl_output *output)
{
    (void)data; (void)output;
}

static void output_scale(void *data, struct wl_output *output, int32_t factor)
{
    (void)data; (void)output; (void)factor;
}

static void output_name(void *data, struct wl_output *output,
                        const char *name)
{
    struct LuminosWayland *wl = data;
    if (wl->output_name && strcmp(name, wl->output_name) == 0) {
        wl->output = output;
        wl->output_matched = 1;
        fprintf(stderr, "[luminos-wallpaper] matched output: %s\n", name);
    }
}

static void output_description(void *data, struct wl_output *output,
                               const char *desc)
{
    (void)data; (void)output; (void)desc;
}

static const struct wl_output_listener output_listener = {
    .geometry    = output_geometry,
    .mode        = output_mode,
    .done        = output_done,
    .scale       = output_scale,
    .name        = output_name,
    .description = output_description,
};

/* ------------------------------------------------------------------ */
/* Seat listener — bind pointer and keyboard                          */
/* ------------------------------------------------------------------ */

static void seat_capabilities(void *data, struct wl_seat *seat,
                              uint32_t caps)
{
    struct LuminosWayland *wl = data;

    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !wl->pointer) {
        wl->pointer = wl_seat_get_pointer(seat);
        input_register_pointer(wl);
    }
    if ((caps & WL_SEAT_CAPABILITY_KEYBOARD) && !wl->keyboard) {
        wl->keyboard = wl_seat_get_keyboard(seat);
        input_register_keyboard(wl);
    }
}

static void seat_name(void *data, struct wl_seat *seat, const char *name)
{
    (void)data; (void)seat; (void)name;
}

static const struct wl_seat_listener seat_listener = {
    .capabilities = seat_capabilities,
    .name         = seat_name,
};

/* ------------------------------------------------------------------ */
/* Registry listener                                                  */
/* ------------------------------------------------------------------ */

static void registry_global(void *data, struct wl_registry *registry,
                            uint32_t name, const char *interface,
                            uint32_t version)
{
    struct LuminosWayland *wl = data;

    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        wl->compositor = wl_registry_bind(registry, name,
                                          &wl_compositor_interface, 4);
    } else if (strcmp(interface, zwlr_layer_shell_v1_interface.name) == 0) {
        wl->layer_shell = wl_registry_bind(registry, name,
                                           &zwlr_layer_shell_v1_interface, 1);
    } else if (strcmp(interface, wl_seat_interface.name) == 0) {
        wl->seat = wl_registry_bind(registry, name,
                                    &wl_seat_interface, 7);
        wl_seat_add_listener(wl->seat, &seat_listener, wl);
    } else if (strcmp(interface, wl_output_interface.name) == 0) {
        struct wl_output *output = wl_registry_bind(registry, name,
                                                    &wl_output_interface, 4);
        wl_output_add_listener(output, &output_listener, wl);
        /* If no specific output requested, use the first one */
        if (!wl->output_name && !wl->output) {
            wl->output = output;
        }
    }
}

static void registry_global_remove(void *data, struct wl_registry *registry,
                                   uint32_t name)
{
    (void)data; (void)registry; (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_global,
    .global_remove = registry_global_remove,
};

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */

int wayland_init(struct LuminosWayland *wl)
{
    memset(wl, 0, sizeof(*wl));
    wl->running = 1;

    wl->display = wl_display_connect(NULL);
    if (!wl->display) {
        fprintf(stderr, "[luminos-wallpaper] failed to connect to Wayland\n");
        return -1;
    }

    wl->registry = wl_display_get_registry(wl->display);
    wl_registry_add_listener(wl->registry, &registry_listener, wl);

    /* First roundtrip: bind globals */
    wl_display_roundtrip(wl->display);
    /* Second roundtrip: receive output info, seat capabilities */
    wl_display_roundtrip(wl->display);

    if (!wl->compositor) {
        fprintf(stderr, "[luminos-wallpaper] no wl_compositor\n");
        return -1;
    }
    if (!wl->layer_shell) {
        fprintf(stderr, "[luminos-wallpaper] no wlr-layer-shell — "
                        "is Hyprland running?\n");
        return -1;
    }

    /* Create surface */
    wl->surface = wl_compositor_create_surface(wl->compositor);
    if (!wl->surface) {
        fprintf(stderr, "[luminos-wallpaper] failed to create surface\n");
        return -1;
    }

    /* Create layer surface on background layer */
    wl->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        wl->layer_shell,
        wl->surface,
        wl->output,   /* NULL = compositor picks primary */
        ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND,
        "luminos-live-wallpaper"
    );
    if (!wl->layer_surface) {
        fprintf(stderr, "[luminos-wallpaper] failed to create layer surface\n");
        return -1;
    }

    /* Anchor to all edges — fills the entire output */
    zwlr_layer_surface_v1_set_anchor(wl->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP    |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT   |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);

    /* No exclusive zone — windows draw over us */
    zwlr_layer_surface_v1_set_exclusive_zone(wl->layer_surface, 0);

    /* Size 0,0 = fill the output */
    zwlr_layer_surface_v1_set_size(wl->layer_surface, 0, 0);

    /* No keyboard interactivity — passive event reception */
    zwlr_layer_surface_v1_set_keyboard_interactivity(wl->layer_surface,
        ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);

    zwlr_layer_surface_v1_add_listener(wl->layer_surface,
                                       &layer_surface_listener, wl);

    /* Commit to trigger configure */
    wl_surface_commit(wl->surface);
    wl_display_roundtrip(wl->display);

    if (!wl->configured) {
        fprintf(stderr, "[luminos-wallpaper] waiting for configure...\n");
        while (!wl->configured && wl->running) {
            if (wl_display_dispatch(wl->display) < 0)
                return -1;
        }
    }

    fprintf(stderr, "[luminos-wallpaper] surface ready: %dx%d\n",
            wl->width, wl->height);

    return 0;
}

void wayland_destroy(struct LuminosWayland *wl)
{
    if (wl->egl_window)
        wl_egl_window_destroy(wl->egl_window);
    if (wl->pointer)
        wl_pointer_destroy(wl->pointer);
    if (wl->keyboard)
        wl_keyboard_destroy(wl->keyboard);
    if (wl->layer_surface)
        zwlr_layer_surface_v1_destroy(wl->layer_surface);
    if (wl->surface)
        wl_surface_destroy(wl->surface);
    if (wl->seat)
        wl_seat_destroy(wl->seat);
    if (wl->compositor)
        wl_compositor_destroy(wl->compositor);
    if (wl->registry)
        wl_registry_destroy(wl->registry);
    if (wl->display)
        wl_display_disconnect(wl->display);
}

int wayland_dispatch(struct LuminosWayland *wl)
{
    /* Flush outgoing requests, dispatch any pending events (non-blocking) */
    if (wl_display_flush(wl->display) < 0)
        return -1;
    return wl_display_dispatch_pending(wl->display);
}
