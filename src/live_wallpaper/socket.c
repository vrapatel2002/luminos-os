#include "socket.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/select.h>

/* ------------------------------------------------------------------ */
/* Command queue (mutex protected)                                    */
/* ------------------------------------------------------------------ */

static struct socket_cmd cmd_queue[SOCKET_CMD_MAX];
static int cmd_head = 0;
static int cmd_tail = 0;
static pthread_mutex_t cmd_mutex = PTHREAD_MUTEX_INITIALIZER;

/* Renderer state for status queries (updated each frame) */
static struct LuminosRenderer *g_renderer_ref = NULL;

static void queue_push(const struct socket_cmd *cmd)
{
    pthread_mutex_lock(&cmd_mutex);
    int next = (cmd_tail + 1) % SOCKET_CMD_MAX;
    if (next != cmd_head) {
        cmd_queue[cmd_tail] = *cmd;
        cmd_tail = next;
    }
    pthread_mutex_unlock(&cmd_mutex);
}

static int queue_pop(struct socket_cmd *out)
{
    pthread_mutex_lock(&cmd_mutex);
    if (cmd_head == cmd_tail) {
        pthread_mutex_unlock(&cmd_mutex);
        return 0;
    }
    *out = cmd_queue[cmd_head];
    cmd_head = (cmd_head + 1) % SOCKET_CMD_MAX;
    pthread_mutex_unlock(&cmd_mutex);
    return 1;
}

/* ------------------------------------------------------------------ */
/* JSON parsing (minimal, no dependency)                              */
/* ------------------------------------------------------------------ */

static const char *json_get_string(const char *json, const char *key,
                                   char *out, size_t outlen)
{
    char pattern[128];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);

    const char *p = strstr(json, pattern);
    if (!p) return NULL;
    p += strlen(pattern);

    /* Skip whitespace and colon */
    while (*p == ' ' || *p == ':' || *p == '\t') p++;

    if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i < outlen - 1) {
            out[i++] = *p++;
        }
        out[i] = '\0';
        return out;
    }
    return NULL;
}

static float intensity_from_string(const char *s)
{
    if (strcmp(s, "low") == 0)    return 0.3f;
    if (strcmp(s, "medium") == 0) return 0.7f;
    if (strcmp(s, "high") == 0)   return 1.0f;
    return 0.7f;
}

static const char *intensity_to_string(float v)
{
    if (v <= 0.4f) return "low";
    if (v <= 0.8f) return "medium";
    return "high";
}

/* ------------------------------------------------------------------ */
/* Client handling                                                    */
/* ------------------------------------------------------------------ */

static void handle_client(int client_fd)
{
    char buf[1024];
    ssize_t n = recv(client_fd, buf, sizeof(buf) - 1, 0);
    if (n <= 0) {
        close(client_fd);
        return;
    }
    buf[n] = '\0';

    /* Strip trailing newline */
    while (n > 0 && (buf[n-1] == '\n' || buf[n-1] == '\r'))
        buf[--n] = '\0';

    char cmd_str[64] = {0};
    json_get_string(buf, "cmd", cmd_str, sizeof(cmd_str));

    struct socket_cmd cmd;
    memset(&cmd, 0, sizeof(cmd));
    char response[512];

    if (strcmp(cmd_str, "set_preset") == 0) {
        cmd.type = CMD_SET_PRESET;
        json_get_string(buf, "preset", cmd.preset, sizeof(cmd.preset));
        char intensity_str[16] = "medium";
        json_get_string(buf, "intensity", intensity_str, sizeof(intensity_str));
        cmd.intensity = intensity_from_string(intensity_str);
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "set_intensity") == 0) {
        cmd.type = CMD_SET_INTENSITY;
        char intensity_str[16] = "medium";
        json_get_string(buf, "intensity", intensity_str, sizeof(intensity_str));
        cmd.intensity = intensity_from_string(intensity_str);
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "pause") == 0) {
        cmd.type = CMD_PAUSE;
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "resume") == 0) {
        cmd.type = CMD_RESUME;
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "suspend") == 0) {
        cmd.type = CMD_SUSPEND;
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "resume_from_suspend") == 0) {
        cmd.type = CMD_RESUME_FROM_SUSPEND;
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else if (strcmp(cmd_str, "status") == 0) {
        /* Read current renderer state (safe — read-only) */
        if (g_renderer_ref) {
            snprintf(response, sizeof(response),
                "{\"status\":\"ok\",\"preset\":\"%s\","
                "\"intensity\":\"%s\","
                "\"paused\":%s,\"suspended\":%s,\"fps\":60}\n",
                g_renderer_ref->current_preset,
                intensity_to_string(g_renderer_ref->intensity),
                g_renderer_ref->paused ? "true" : "false",
                g_renderer_ref->suspended ? "true" : "false");
        } else {
            snprintf(response, sizeof(response),
                "{\"status\":\"ok\",\"preset\":\"none\","
                "\"paused\":false,\"suspended\":false,\"fps\":0}\n");
        }

    } else if (strcmp(cmd_str, "quit") == 0) {
        cmd.type = CMD_QUIT;
        queue_push(&cmd);
        snprintf(response, sizeof(response), "{\"status\":\"ok\"}\n");

    } else {
        snprintf(response, sizeof(response),
            "{\"status\":\"error\",\"message\":\"unknown command: %s\"}\n",
            cmd_str);
    }

    send(client_fd, response, strlen(response), 0);
    close(client_fd);
}

/* ------------------------------------------------------------------ */
/* Socket thread                                                      */
/* ------------------------------------------------------------------ */

static int server_fd = -1;
static pthread_t socket_thread;
static volatile int socket_running = 0;
static char socket_path[256];

static void *socket_thread_fn(void *arg)
{
    (void)arg;

    while (socket_running) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(server_fd, &fds);

        struct timeval tv;
        tv.tv_sec  = 0;
        tv.tv_usec = 100000; /* 100ms timeout */

        int ret = select(server_fd + 1, &fds, NULL, NULL, &tv);
        if (ret > 0 && FD_ISSET(server_fd, &fds)) {
            int client_fd = accept(server_fd, NULL, NULL);
            if (client_fd >= 0)
                handle_client(client_fd);
        }
    }

    return NULL;
}

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */

int socket_start(const char *path)
{
    if (path)
        strncpy(socket_path, path, sizeof(socket_path) - 1);
    else
        strncpy(socket_path, LUMINOS_SOCKET_PATH, sizeof(socket_path) - 1);

    /* Remove stale socket */
    unlink(socket_path);

    server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("[luminos-wallpaper] socket");
        return -1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("[luminos-wallpaper] bind");
        close(server_fd);
        server_fd = -1;
        return -1;
    }

    if (listen(server_fd, 4) < 0) {
        perror("[luminos-wallpaper] listen");
        close(server_fd);
        server_fd = -1;
        return -1;
    }

    socket_running = 1;
    if (pthread_create(&socket_thread, NULL, socket_thread_fn, NULL) != 0) {
        perror("[luminos-wallpaper] pthread_create");
        close(server_fd);
        server_fd = -1;
        return -1;
    }

    fprintf(stderr, "[luminos-wallpaper] socket listening: %s\n", socket_path);
    return 0;
}

void socket_stop(void)
{
    socket_running = 0;
    if (server_fd >= 0) {
        pthread_join(socket_thread, NULL);
        close(server_fd);
        unlink(socket_path);
        server_fd = -1;
    }
}

int socket_process_queue(struct LuminosRenderer *r, int *running)
{
    g_renderer_ref = r;

    struct socket_cmd cmd;
    while (queue_pop(&cmd)) {
        switch (cmd.type) {
        case CMD_SET_PRESET:
            renderer_load_preset(r, cmd.preset);
            renderer_set_intensity(r, cmd.intensity);
            break;
        case CMD_SET_INTENSITY:
            renderer_set_intensity(r, cmd.intensity);
            break;
        case CMD_PAUSE:
            renderer_pause(r);
            break;
        case CMD_RESUME:
            renderer_resume(r);
            break;
        case CMD_SUSPEND:
            renderer_suspend(r);
            break;
        case CMD_RESUME_FROM_SUSPEND:
            renderer_resume(r);
            break;
        case CMD_QUIT:
            *running = 0;
            return CMD_QUIT;
        default:
            break;
        }
    }
    return CMD_NONE;
}
