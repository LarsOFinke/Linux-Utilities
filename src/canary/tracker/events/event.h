#ifndef FSTRACKER_EVENT_H
#define FSTRACKER_EVENT_H

#include <linux/limits.h>
#include <stdint.h>
#include <sys/types.h>
#include <time.h>

typedef struct {
    struct timespec timestamp;
    uint64_t mask;
    pid_t pid;
    char path[PATH_MAX];
} FsEvent;

#endif
