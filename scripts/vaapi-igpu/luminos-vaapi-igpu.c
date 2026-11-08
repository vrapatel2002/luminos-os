// luminos-vaapi-igpu — make ffmpeg's *default* VA-API device the AMD iGPU render node.
// [CHANGE: claude-code | 2026-11-08]  BUG-234 / DECISION 180
//
// WHY: with no device string, ffmpeg's vaapi_device_create() opens /dev/dri/renderD128
// ("device 0") and gives up on any error other than ENOENT. On this box renderD128 is
// the RTX 4050, gated root:dgpu 0660 by BUG-184's udev rule, so the open fails with
// EACCES and the AMD node is never tried: Qt Multimedia (and anything else on ffmpeg)
// silently loses hardware decode. This LD_PRELOAD fills in the iGPU node — found by
// PCI vendor 0x1002 in /sys, never by number, because renderD numbering is probe order.
// It touches nothing else: explicit device strings and every other hw type pass through.
//
// Build: gcc -O2 -shared -fPIC -o libluminos-vaapi-igpu.so luminos-vaapi-igpu.c -ldl
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

typedef struct AVBufferRef AVBufferRef;
typedef struct AVDictionary AVDictionary;
enum { LUMINOS_AV_HWDEVICE_TYPE_VAAPI = 3 };   // stable in libavutil's enum AVHWDeviceType since 2017

static const char *igpu_node(void) {
    static char path[32];
    static int done;
    if (done) return path[0] ? path : NULL;
    done = 1;
    for (int n = 128; n < 144; n++) {
        char v[64], id[16] = {0};
        snprintf(v, sizeof v, "/sys/class/drm/renderD%d/device/vendor", n);
        FILE *f = fopen(v, "r");
        if (!f) continue;
        if (!fgets(id, sizeof id, f)) id[0] = 0;
        fclose(f);
        if (!strncmp(id, "0x1002", 6)) { snprintf(path, sizeof path, "/dev/dri/renderD%d", n); return path; }
    }
    return NULL;
}

static void *resolve(void) {
    void *p = dlsym(RTLD_NEXT, "av_hwdevice_ctx_create");
    if (p) return p;
    // Preloaded before libavutil is mapped (it arrives later via a Qt plugin dlopen).
    static const char *libs[] = {"libavutil.so.61", "libavutil.so.60", "libavutil.so.59", "libavutil.so", NULL};
    for (int i = 0; libs[i]; i++) {
        void *h = dlopen(libs[i], RTLD_NOW | RTLD_GLOBAL);
        if (h && (p = dlsym(h, "av_hwdevice_ctx_create"))) return p;
    }
    return NULL;
}

int av_hwdevice_ctx_create(AVBufferRef **ctx, int type, const char *device, AVDictionary *opts, int flags) {
    static int (*real)(AVBufferRef **, int, const char *, AVDictionary *, int);
    if (!real) real = resolve();
    if (!real) return -38;   // AVERROR(ENOSYS): no libavutil at all
    if (type == LUMINOS_AV_HWDEVICE_TYPE_VAAPI && (!device || !*device)) {
        const char *n = igpu_node();
        if (n) device = n;
    }
    return real(ctx, type, device, opts, flags);
}
