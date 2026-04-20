#ifndef LUMINOS_POWER_H
#define LUMINOS_POWER_H

#include "renderer.h"

/*
 * Check if the system is on battery power.
 * Returns 1 if on battery, 0 if plugged in or unknown.
 */
int power_on_battery(void);

/*
 * Auto-manage renderer based on power state.
 * Pauses on battery, resumes on AC.
 * Call periodically from main loop.
 */
void power_check(struct LuminosRenderer *r);

#endif
