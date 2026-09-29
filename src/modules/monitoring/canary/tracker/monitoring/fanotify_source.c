#define _GNU_SOURCE
#include "fanotify_source.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/fanotify.h>
#include <unistd.h>

static uint64_t tracked_mask(void)
{
    uint64_t mask = FAN_OPEN |
                    FAN_ACCESS |
                    FAN_MODIFY |
                    FAN_CLOSE_WRITE |
                    FAN_CLOSE_NOWRITE;
#ifdef FAN_OPEN_EXEC
    mask |= FAN_OPEN_EXEC;
#endif
    return mask;
}

static void event_fd_to_path(int fd, char *path, size_t path_size)
{
    path[0] = '\0';

    if (fd < 0)
        return;

    char proc_path[64];
    snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", fd);

    ssize_t n = readlink(proc_path, path, path_size - 1);
    if (n >= 0)
        path[n] = '\0';
}

int fanotify_source_open(FanotifySource *source, const char *target_path, char *err, size_t err_size)
{
    memset(source, 0, sizeof(*source));
    source->fd = -1;

    source->fd = fanotify_init(FAN_CLASS_NOTIF | FAN_CLOEXEC,
                               O_RDONLY | O_LARGEFILE | O_CLOEXEC);
    if (source->fd < 0) {
        snprintf(err, err_size, "fanotify_init failed: %s", strerror(errno));
        return -1;
    }

    if (fanotify_mark(source->fd,
                      FAN_MARK_ADD,
                      tracked_mask(),
                      AT_FDCWD,
                      target_path) < 0) {
        snprintf(err, err_size, "fanotify_mark('%s') failed: %s", target_path, strerror(errno));
        close(source->fd);
        source->fd = -1;
        return -1;
    }

    return 0;
}

int fanotify_source_next(FanotifySource *source, FsEvent *event, char *err, size_t err_size)
{
    for (;;) {
        if (source->offset >= source->length) {
            ssize_t n;
            do {
                n = read(source->fd, source->buffer, sizeof(source->buffer));
            } while (n < 0 && errno == EINTR);

            if (n < 0) {
                snprintf(err, err_size, "fanotify read failed: %s", strerror(errno));
                return -1;
            }

            if (n == 0) {
                snprintf(err, err_size, "fanotify returned EOF");
                return -1;
            }

            source->length = (size_t)n;
            source->offset = 0;
        }

        size_t remaining = source->length - source->offset;
        struct fanotify_event_metadata *metadata =
            (struct fanotify_event_metadata *)(source->buffer + source->offset);

        if (remaining < sizeof(*metadata) || metadata->event_len < sizeof(*metadata) || metadata->event_len > remaining) {
            snprintf(err, err_size, "invalid fanotify event record");
            return -1;
        }

        source->offset += metadata->event_len;

        if (metadata->vers != FANOTIFY_METADATA_VERSION) {
            snprintf(err, err_size, "fanotify metadata version mismatch: kernel=%u userspace=%u",
                     metadata->vers, FANOTIFY_METADATA_VERSION);
            if (metadata->fd >= 0)
                close(metadata->fd);
            return -1;
        }

        memset(event, 0, sizeof(*event));
        clock_gettime(CLOCK_REALTIME, &event->timestamp);
        event->mask = metadata->mask;
        event->pid = metadata->pid;

        if (metadata->fd >= 0) {
            event_fd_to_path(metadata->fd, event->path, sizeof(event->path));
            close(metadata->fd);
        }

        return 0;
    }
}

void fanotify_source_close(FanotifySource *source)
{
    if (source->fd >= 0)
        close(source->fd);

    source->fd = -1;
    source->length = 0;
    source->offset = 0;
}
