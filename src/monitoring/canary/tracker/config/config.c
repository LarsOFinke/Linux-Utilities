#include "config.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int copy_value(char *dst, size_t dst_size, const char *src, const char *name, char *err, size_t err_size)
{
    if (!src || !*src) {
        snprintf(err, err_size, "%s must not be empty", name);
        return -1;
    }

    if (strlen(src) >= dst_size) {
        snprintf(err, err_size, "%s is too long", name);
        return -1;
    }

    strcpy(dst, src);
    return 0;
}

static char *trim(char *s)
{
    while (*s == ' ' || *s == '\t')
        s++;

    char *end = s + strlen(s);
    while (end > s && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\n' || end[-1] == '\r'))
        *--end = '\0';

    return s;
}

static void load_defaults(TrackerConfig *config)
{
    strcpy(config->target_path, "/tmp/secret.txt");
    strcpy(config->log_path, "./fs-events.jsonl");
    config->action_path[0] = '\0';
}

static int load_file(TrackerConfig *config, const char *path, char *err, size_t err_size)
{
    FILE *file = fopen(path, "r");
    if (!file) {
        snprintf(err, err_size, "cannot open config '%s': %s", path, strerror(errno));
        return -1;
    }

    char line[PATH_MAX + 64];
    unsigned line_no = 0;

    while (fgets(line, sizeof(line), file)) {
        line_no++;
        char *text = trim(line);

        if (*text == '\0' || *text == '#')
            continue;

        char *equals = strchr(text, '=');
        if (!equals) {
            snprintf(err, err_size, "invalid config line %u", line_no);
            fclose(file);
            return -1;
        }

        *equals = '\0';
        char *key = trim(text);
        char *value = trim(equals + 1);

        if (strcmp(key, "TRACK_PATH") == 0) {
            if (copy_value(config->target_path, sizeof(config->target_path), value, key, err, err_size) < 0) {
                fclose(file);
                return -1;
            }
        } else if (strcmp(key, "TRACK_LOG") == 0) {
            if (copy_value(config->log_path, sizeof(config->log_path), value, key, err, err_size) < 0) {
                fclose(file);
                return -1;
            }
        } else if (strcmp(key, "TRACK_ACTION") == 0) {
            if (copy_value(config->action_path, sizeof(config->action_path), value, key, err, err_size) < 0) {
                fclose(file);
                return -1;
            }
        } else {
            snprintf(err, err_size, "unknown config key '%s' on line %u", key, line_no);
            fclose(file);
            return -1;
        }
    }

    if (ferror(file)) {
        snprintf(err, err_size, "error reading config '%s'", path);
        fclose(file);
        return -1;
    }

    fclose(file);
    return 0;
}

static int validate_args(int argc, char **argv, char *err, size_t err_size)
{
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0)
            return 1;

        if (strcmp(argv[i], "--config") == 0 || strcmp(argv[i], "--path") == 0 ||
            strcmp(argv[i], "--log") == 0 || strcmp(argv[i], "--action") == 0) {
            if (i + 1 >= argc) {
                snprintf(err, err_size, "%s requires a value", argv[i]);
                return -1;
            }
            i++;
            continue;
        }

        snprintf(err, err_size, "unknown argument '%s'", argv[i]);
        return -1;
    }

    return 0;
}

static int load_config_files(TrackerConfig *config, int argc, char **argv, char *err, size_t err_size)
{
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0) {
            if (load_file(config, argv[++i], err, err_size) < 0)
                return -1;
        } else if (strcmp(argv[i], "--path") == 0 || strcmp(argv[i], "--log") == 0 ||
               strcmp(argv[i], "--action") == 0) {
            i++;
        }
    }
    return 0;
}

static int load_env(TrackerConfig *config, char *err, size_t err_size)
{
    const char *target = getenv("TRACK_PATH");
    const char *log = getenv("TRACK_LOG");
    const char *action = getenv("TRACK_ACTION");

    if (target && copy_value(config->target_path, sizeof(config->target_path), target, "TRACK_PATH", err, err_size) < 0)
        return -1;

    if (log && copy_value(config->log_path, sizeof(config->log_path), log, "TRACK_LOG", err, err_size) < 0)
        return -1;

    if (action && copy_value(config->action_path, sizeof(config->action_path), action, "TRACK_ACTION", err, err_size) < 0)
        return -1;

    return 0;
}

static int load_cli_overrides(TrackerConfig *config, int argc, char **argv, char *err, size_t err_size)
{
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0) {
            i++;
        } else if (strcmp(argv[i], "--path") == 0) {
            if (copy_value(config->target_path, sizeof(config->target_path), argv[++i], "--path", err, err_size) < 0)
                return -1;
        } else if (strcmp(argv[i], "--log") == 0) {
            if (copy_value(config->log_path, sizeof(config->log_path), argv[++i], "--log", err, err_size) < 0)
                return -1;
        } else if (strcmp(argv[i], "--action") == 0) {
            if (copy_value(config->action_path, sizeof(config->action_path), argv[++i], "--action", err, err_size) < 0)
                return -1;
        }
    }

    return 0;
}

int tracker_config_load(TrackerConfig *config, int argc, char **argv, char *err, size_t err_size)
{
    load_defaults(config);

    int validation = validate_args(argc, argv, err, err_size);
    if (validation != 0)
        return validation;

    if (load_config_files(config, argc, argv, err, err_size) < 0)
        return -1;

    if (load_env(config, err, err_size) < 0)
        return -1;

    if (load_cli_overrides(config, argc, argv, err, err_size) < 0)
        return -1;

    if (strcmp(config->target_path, config->log_path) == 0) {
        snprintf(err, err_size, "target and log path must be different");
        return -1;
    }

    return 0;
}

void tracker_config_print_usage(const char *program_name)
{
    fprintf(stderr,
            "Usage: %s [--config FILE] [--path FILE] [--log FILE] [--action FILE]\n"
            "\n"
            "Precedence: defaults < config file < environment < CLI overrides.\n"
            "Environment: TRACK_PATH, TRACK_LOG, TRACK_ACTION\n",
            program_name);
}
