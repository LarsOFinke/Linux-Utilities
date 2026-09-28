#ifndef FSTRACKER_FANOTIFY_SOURCE_H
#define FSTRACKER_FANOTIFY_SOURCE_H

#include "event.h"

#include <stddef.h>
#include <stdint.h>

#define FSTRACKER_EVENT_BUFFER_SIZE 16384

typedef struct {
    int fd;
    unsigned char buffer[FSTRACKER_EVENT_BUFFER_SIZE] __attribute__((aligned(8)));
    size_t length;
    size_t offset;
} FanotifySource;

int fanotify_source_open(FanotifySource *source, const char *target_path, char *err, size_t err_size);
int fanotify_source_next(FanotifySource *source, FsEvent *event, char *err, size_t err_size);
void fanotify_source_close(FanotifySource *source);

#endif
