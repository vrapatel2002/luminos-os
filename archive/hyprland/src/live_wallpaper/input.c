#include "input.h"

#include <stdio.h>
#include <wayland-client.h>

static struct LuminosRenderer *g_renderer = NULL;
static struct LuminosWayland  *g_wayland  = NULL;

void input_set_renderer(struct LuminosRenderer *r)
{
    g_renderer = r;
}

/* ------------------------------------------------------------------ */
/* Pointer events                                                     */
/* ------------------------------------------------------------------ */

static void pointer_enter(void *data, struct wl_pointer *pointer,
                          uint32_t serial, struct wl_surface *surface,
                          wl_fixed_t sx, wl_fixed_t sy)
{
    (void)data; (void)pointer; (void)serial; (void)surface;
    if (!g_renderer || !g_wayland) return;

    float x = wl_fixed_to_double(sx) / (float)g_wayland->width;
    float y = 1.0f - wl_fixed_to_double(sy) / (float)g_wayland->height;
    renderer_set_mouse(g_renderer, x, y);
}

static void pointer_leave(void *data, struct wl_pointer *pointer,
                          uint32_t serial, struct wl_surface *surface)
{
    (void)data; (void)pointer; (void)serial; (void)surface;
}

static void pointer_motion(void *data, struct wl_pointer *pointer,
                           uint32_t time, wl_fixed_t sx, wl_fixed_t sy)
{
    (void)data; (void)pointer; (void)time;
    if (!g_renderer || !g_wayland) return;

    float x = wl_fixed_to_double(sx) / (float)g_wayland->width;
    float y = 1.0f - wl_fixed_to_double(sy) / (float)g_wayland->height;

    /* Clamp to 0-1 */
    if (x < 0.0f) x = 0.0f;
    if (x > 1.0f) x = 1.0f;
    if (y < 0.0f) y = 0.0f;
    if (y > 1.0f) y = 1.0f;

    renderer_set_mouse(g_renderer, x, y);
}

static void pointer_button(void *data, struct wl_pointer *pointer,
                           uint32_t serial, uint32_t time,
                           uint32_t button, uint32_t state)
{
    (void)data; (void)pointer; (void)serial; (void)time;
    (void)button;

    /* Treat mouse click as a key event for the pulse effect */
    if (g_renderer && state == WL_POINTER_BUTTON_STATE_PRESSED)
        renderer_on_key(g_renderer);
}

static void pointer_axis(void *data, struct wl_pointer *pointer,
                         uint32_t time, uint32_t axis, wl_fixed_t value)
{
    (void)data; (void)pointer; (void)time; (void)axis; (void)value;
}

static const struct wl_pointer_listener pointer_listener = {
    .enter  = pointer_enter,
    .leave  = pointer_leave,
    .motion = pointer_motion,
    .button = pointer_button,
    .axis   = pointer_axis,
};

void input_register_pointer(struct LuminosWayland *wl)
{
    g_wayland = wl;
    if (wl->pointer)
        wl_pointer_add_listener(wl->pointer, &pointer_listener, wl);
}

/* ------------------------------------------------------------------ */
/* Keyboard events                                                    */
/* ------------------------------------------------------------------ */

static void keyboard_keymap(void *data, struct wl_keyboard *keyboard,
                            uint32_t format, int32_t fd, uint32_t size)
{
    (void)data; (void)keyboard; (void)format; (void)size;
    /* We don't need the keymap — just close the fd */
    close(fd);
}

static void keyboard_enter(void *data, struct wl_keyboard *keyboard,
                           uint32_t serial, struct wl_surface *surface,
                           struct wl_array *keys)
{
    (void)data; (void)keyboard; (void)serial;
    (void)surface; (void)keys;
}

static void keyboard_leave(void *data, struct wl_keyboard *keyboard,
                           uint32_t serial, struct wl_surface *surface)
{
    (void)data; (void)keyboard; (void)serial; (void)surface;
}

static void keyboard_key(void *data, struct wl_keyboard *keyboard,
                         uint32_t serial, uint32_t time,
                         uint32_t key, uint32_t state)
{
    (void)data; (void)keyboard; (void)serial; (void)time; (void)key;

    /* Only trigger on key press, not release */
    if (g_renderer && state == WL_KEYBOARD_KEY_STATE_PRESSED)
        renderer_on_key(g_renderer);
}

static void keyboard_modifiers(void *data, struct wl_keyboard *keyboard,
                               uint32_t serial, uint32_t mods_depressed,
                               uint32_t mods_latched, uint32_t mods_locked,
                               uint32_t group)
{
    (void)data; (void)keyboard; (void)serial;
    (void)mods_depressed; (void)mods_latched;
    (void)mods_locked; (void)group;
}

static void keyboard_repeat_info(void *data, struct wl_keyboard *keyboard,
                                 int32_t rate, int32_t delay)
{
    (void)data; (void)keyboard; (void)rate; (void)delay;
}

static const struct wl_keyboard_listener keyboard_listener = {
    .keymap      = keyboard_keymap,
    .enter       = keyboard_enter,
    .leave       = keyboard_leave,
    .key         = keyboard_key,
    .modifiers   = keyboard_modifiers,
    .repeat_info = keyboard_repeat_info,
};

void input_register_keyboard(struct LuminosWayland *wl)
{
    g_wayland = wl;
    if (wl->keyboard)
        wl_keyboard_add_listener(wl->keyboard, &keyboard_listener, wl);
}
