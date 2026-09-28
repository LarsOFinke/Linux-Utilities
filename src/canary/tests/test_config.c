#define _GNU_SOURCE
#include "config.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    char template[] = "/tmp/fs-tracker-config-XXXXXX";
    int fd = mkstemp(template);
    assert(fd >= 0);

    FILE *file = fdopen(fd, "w");
    assert(file != NULL);
    fputs("TRACK_PATH=/from-config\nTRACK_LOG=/config-log.jsonl\nTRACK_ACTION=/config-action\n", file);
    fclose(file);

    assert(setenv("TRACK_PATH", "/from-env", 1) == 0);
    assert(setenv("TRACK_LOG", "/env-log.jsonl", 1) == 0);

    char *argv[] = {
        "fs-tracker",
        "--config", template,
        "--path", "/from-cli",
        NULL
    };

    TrackerConfig config;
    char err[256] = {0};
    int result = tracker_config_load(&config, 5, argv, err, sizeof(err));

    assert(result == 0);
    assert(strcmp(config.target_path, "/from-cli") == 0);
    assert(strcmp(config.log_path, "/env-log.jsonl") == 0);
    assert(strcmp(config.action_path, "/config-action") == 0);

    unsetenv("TRACK_PATH");
    unsetenv("TRACK_LOG");
    unlink(template);

    return 0;
}
