#ifndef LUMINOS_SOCKET_H
#define LUMINOS_SOCKET_H

#include "renderer.h"

#define LUMINOS_SOCKET_PATH "/tmp/luminos-wallpaper.sock"
#define SOCKET_CMD_MAX 32

/* Command types */
enum socket_cmd_type {
    CMD_NONE = 0,
    CMD_SET_PRESET,
    CMD_SET_INTENSITY,
    CMD_PAUSE,
    CMD_RESUME,
    CMD_SUSPEND,
    CMD_RESUME_FROM_SUSPEND,
    CMD_STATUS,
    CMD_QUIT,
};

/* Queued command */
struct socket_cmd {
    enum socket_cmd_type type;
    char preset[64];
    float intensity;
};

/*
 * Start the socket listener thread.
 * socket_path: path to Unix socket (NULL = default)
 */
int  socket_start(const char *socket_path);

/*
 * Stop the socket thread and clean up.
 */
void socket_stop(void);

/*
 * Process queued commands on the main thread.
 * Returns CMD_QUIT if quit was requested, CMD_NONE otherwise.
 * Sets *running = 0 on quit.
 */
int  socket_process_queue(struct LuminosRenderer *r, int *running);

#endif
