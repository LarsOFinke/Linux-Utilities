#ifndef FSTRACKER_CONFIG_H
#define FSTRACKER_CONFIG_H

#include <linux/limits.h>
#include <stddef.h>

typedef struct {
    char target_path[PATH_MAX];
    char log_path[PATH_MAX];
    char action_path[PATH_MAX];
} TrackerConfig;

/*
 * Loads configuration with deterministic precedence:
 * defaults < --config file < environment < --path/--log CLI overrides.
 * Returns 1 for --help, 0 on success, -1 on error.
 */
int tracker_config_load(TrackerConfig *config, int argc, char **argv, char *err, size_t err_size);
void tracker_config_print_usage(const char *program_name);

#endif
