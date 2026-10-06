#define _POSIX_C_SOURCE 200809L
#include "action.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

int action_run(const char *path, const FsEvent *event, char *err, size_t err_size)
{
    if (!path || !*path)
        return 0;

    pid_t child = fork();
    if (child < 0) {
        snprintf(err, err_size, "cannot start action '%s': %s", path, strerror(errno));
        return -1;
    }

    if (child == 0) {
        char mask[32];
        char pid[32];
        snprintf(mask, sizeof(mask), "%llu", (unsigned long long)event->mask);
        snprintf(pid, sizeof(pid), "%d", event->pid);
        execl(path, path, event->path, mask, pid, (char *)NULL);
        dprintf(STDERR_FILENO, "action '%s' failed: %s\n", path, strerror(errno));
        _exit(127);
    }

    int status;
    while (waitpid(child, &status, 0) < 0) {
        if (errno == EINTR)
            continue;
        snprintf(err, err_size, "cannot wait for action '%s': %s", path, strerror(errno));
        return -1;
    }

    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        snprintf(err, err_size, "action '%s' exited unsuccessfully", path);
        return -1;
    }

    return 0;
}