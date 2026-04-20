#ifndef LUMINOS_INPUT_H
#define LUMINOS_INPUT_H

#include "wayland.h"
#include "renderer.h"

/* Register pointer and keyboard listeners on the Wayland seat */
void input_register_pointer(struct LuminosWayland *wl);
void input_register_keyboard(struct LuminosWayland *wl);

/* Set the renderer that receives input events */
void input_set_renderer(struct LuminosRenderer *r);

#endif
