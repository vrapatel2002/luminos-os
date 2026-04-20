/*
 * luminos-live-wallpaper — Luminos OS live wallpaper renderer
 *
 * Native C program that renders GLSL shader presets on the desktop
 * background via wlr-layer-shell on Wayland/Hyprland.
 *
 * Runs on AMD iGPU exclusively. Controlled via Unix socket.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <math.h>

#include "wayland.h"
#include "egl.h"
#include "renderer.h"
#include "input.h"
#include "socket.h"
#include "power.h"

/* ------------------------------------------------------------------ */
/* Globals                                                            */
/* ------------------------------------------------------------------ */

static struct LuminosWayland  g_wl;
static struct LuminosEGL      g_egl;
static struct LuminosRenderer g_renderer;

/* ------------------------------------------------------------------ */
/* Signal handling                                                    */
/* ------------------------------------------------------------------ */

static void signal_handler(int sig)
{
    if (sig == SIGTERM || sig == SIGINT) {
        g_wl.running = 0;
    } else if (sig == SIGUSR1) {
        renderer_pause(&g_renderer);
    } else if (sig == SIGUSR2) {
        renderer_resume(&g_renderer);
    }
}

static void setup_signals(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);

    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT,  &sa, NULL);
    sigaction(SIGUSR1, &sa, NULL);
    sigaction(SIGUSR2, &sa, NULL);

    /* Ignore SIGPIPE from socket writes */
    signal(SIGPIPE, SIG_IGN);
}

/* ------------------------------------------------------------------ */
/* Frame timing                                                       */
/* ------------------------------------------------------------------ */

static const double FRAME_TIME = 1.0 / 60.0; /* 16.67ms */

static void frame_sleep_to_60fps(double frame_start)
{
    double elapsed = renderer_get_time() - frame_start;
    double remaining = FRAME_TIME - elapsed;

    if (remaining > 0.001) {
        struct timespec ts;
        ts.tv_sec  = 0;
        ts.tv_nsec = (long)(remaining * 1e9);
        nanosleep(&ts, NULL);
    }
}

/* ------------------------------------------------------------------ */
/* Argument parsing                                                   */
/* ------------------------------------------------------------------ */

static void print_usage(const char *prog)
{
    fprintf(stderr,
        "Usage: %s [options]\n"
        "Options:\n"
        "  --preset particles|aurora|geometric  (default: particles)\n"
        "  --intensity low|medium|high          (default: medium)\n"
        "  --output [wayland output name]       (default: primary)\n"
        "  --socket [path]                      (default: %s)\n"
        "  --help                               show this message\n",
        prog, LUMINOS_SOCKET_PATH);
}

static float parse_intensity(const char *s)
{
    if (strcmp(s, "low") == 0)    return 0.3f;
    if (strcmp(s, "medium") == 0) return 0.7f;
    if (strcmp(s, "high") == 0)   return 1.0f;
    fprintf(stderr, "[luminos-wallpaper] unknown intensity '%s', using medium\n", s);
    return 0.7f;
}

/* ------------------------------------------------------------------ */
/* Main                                                               */
/* ------------------------------------------------------------------ */

int main(int argc, char *argv[])
{
    const char *preset      = "particles";
    float       intensity   = 0.7f;
    const char *output_name = NULL;
    const char *socket_path = NULL;

    /* Parse arguments */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--preset") == 0 && i + 1 < argc) {
            preset = argv[++i];
        } else if (strcmp(argv[i], "--intensity") == 0 && i + 1 < argc) {
            intensity = parse_intensity(argv[++i]);
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            output_name = argv[++i];
        } else if (strcmp(argv[i], "--socket") == 0 && i + 1 < argc) {
            socket_path = argv[++i];
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "[luminos-wallpaper] unknown argument: %s\n",
                    argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    fprintf(stderr, "[luminos-wallpaper] starting: preset=%s intensity=%.1f\n",
            preset, intensity);

    setup_signals();

    /* 1. Wayland init */
    g_wl.output_name = output_name;
    if (wayland_init(&g_wl) < 0) {
        fprintf(stderr, "[luminos-wallpaper] wayland init failed\n");
        return 1;
    }

    /* 2. EGL init — force AMD iGPU */
    if (egl_init(&g_egl, &g_wl) < 0) {
        fprintf(stderr, "[luminos-wallpaper] EGL init failed\n");
        wayland_destroy(&g_wl);
        return 1;
    }

    /* 3. Renderer init */
    if (renderer_init(&g_renderer, preset, intensity,
                      g_wl.width, g_wl.height) < 0) {
        fprintf(stderr, "[luminos-wallpaper] renderer init failed\n");
        egl_destroy(&g_egl);
        wayland_destroy(&g_wl);
        return 1;
    }

    /* 4. Connect input to renderer */
    input_set_renderer(&g_renderer);

    /* 5. Start socket thread */
    if (socket_start(socket_path) < 0) {
        fprintf(stderr, "[luminos-wallpaper] socket init failed "
                        "(non-fatal, continuing without control)\n");
    }

    fprintf(stderr, "[luminos-wallpaper] entering main loop\n");

    /* Power check interval: every 30 seconds */
    double last_power_check = renderer_get_time();
    const double POWER_CHECK_INTERVAL = 30.0;

    /* 6. Main loop */
    while (g_wl.running) {
        double frame_start = renderer_get_time();

        /* Process socket commands */
        socket_process_queue(&g_renderer, &g_wl.running);
        if (!g_wl.running)
            break;

        /* Dispatch Wayland events */
        if (wl_display_prepare_read(g_wl.display) == 0) {
            wl_display_read_events(g_wl.display);
        }
        wayland_dispatch(&g_wl);

        /* Update renderer size if changed */
        if (g_renderer.width != g_wl.width ||
            g_renderer.height != g_wl.height) {
            renderer_set_size(&g_renderer, g_wl.width, g_wl.height);
        }

        /* Periodic power check */
        if (frame_start - last_power_check > POWER_CHECK_INTERVAL) {
            power_check(&g_renderer);
            last_power_check = frame_start;
        }

        /* Render frame or sleep */
        if (!g_renderer.suspended && !g_renderer.paused) {
            renderer_frame(&g_renderer);
            egl_swap(&g_egl);
            wl_surface_commit(g_wl.surface);
        } else {
            /* When suspended/paused: sleep 100ms, loop to check socket */
            struct timespec ts = { 0, 100000000L }; /* 100ms */
            nanosleep(&ts, NULL);
            continue; /* skip frame timing */
        }

        /* Frame timing */
        frame_sleep_to_60fps(frame_start);
    }

    /* 7. Cleanup */
    fprintf(stderr, "[luminos-wallpaper] shutting down\n");
    socket_stop();
    renderer_destroy(&g_renderer);
    egl_destroy(&g_egl);
    wayland_destroy(&g_wl);

    return 0;
}
