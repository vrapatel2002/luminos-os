#include "power.h"

#include <stdio.h>
#include <string.h>

static int last_battery_state = -1; /* -1 = unknown */

int power_on_battery(void)
{
    FILE *f = fopen("/sys/class/power_supply/BAT0/status", "r");
    if (!f)
        f = fopen("/sys/class/power_supply/BAT1/status", "r");
    if (!f)
        return 0; /* assume plugged in if we can't read */

    char buf[64];
    if (fgets(buf, sizeof(buf), f) == NULL) {
        fclose(f);
        return 0;
    }
    fclose(f);

    /* Status is "Charging", "Discharging", "Full", "Not charging" */
    if (strncmp(buf, "Discharging", 11) == 0)
        return 1;

    return 0;
}

void power_check(struct LuminosRenderer *r)
{
    int on_battery = power_on_battery();

    if (on_battery != last_battery_state) {
        if (on_battery && !r->paused && !r->suspended) {
            fprintf(stderr, "[luminos-wallpaper] on battery — pausing\n");
            renderer_pause(r);
        } else if (!on_battery && r->paused && !r->suspended) {
            fprintf(stderr, "[luminos-wallpaper] on AC — resuming\n");
            renderer_resume(r);
        }
        last_battery_state = on_battery;
    }
}
