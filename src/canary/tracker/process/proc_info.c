#define _GNU_SOURCE
#include "proc_info.h"

#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static void process_info_reset(ProcessInfo *info, pid_t pid)
{
    memset(info, 0, sizeof(*info));
    info->pid = pid;
    info->ppid = -1;
    info->uid = (uid_t)-1;
    info->euid = (uid_t)-1;
    info->gid = (gid_t)-1;
    info->egid = (gid_t)-1;
    info->session_id = -1;
    info->tty_nr = -1;
    info->start_time = -1;
}

static void read_status(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/status", info->pid);

    FILE *file = fopen(path, "r");
    if (!file)
        return;

    char line[512];
    while (fgets(line, sizeof(line), file)) {
        unsigned real_uid;
        unsigned effective_uid;
        unsigned saved_uid;
        unsigned fs_uid;
        unsigned real_gid;
        unsigned effective_gid;
        unsigned saved_gid;
        unsigned fs_gid;
        int ppid;

        if (sscanf(line, "Name:%255s", info->comm) == 1)
            continue;
        if (sscanf(line, "Uid:%u %u %u %u", &real_uid, &effective_uid, &saved_uid, &fs_uid) == 4) {
            info->uid = (uid_t)real_uid;
            info->euid = (uid_t)effective_uid;
        } else if (sscanf(line, "Uid:%u", &real_uid) == 1) {
            info->uid = (uid_t)real_uid;
            info->euid = (uid_t)real_uid;
        } else if (sscanf(line, "Gid:%u %u %u %u", &real_gid, &effective_gid, &saved_gid, &fs_gid) == 4) {
            info->gid = (gid_t)real_gid;
            info->egid = (gid_t)effective_gid;
        } else if (sscanf(line, "Gid:%u", &real_gid) == 1) {
            info->gid = (gid_t)real_gid;
            info->egid = (gid_t)real_gid;
        } else if (sscanf(line, "PPid:%d", &ppid) == 1) {
            info->ppid = (pid_t)ppid;
        }
    }

    fclose(file);
}

static void read_stat(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/stat", info->pid);

    FILE *file = fopen(path, "r");
    if (!file)
        return;

    char buffer[4096];
    if (!fgets(buffer, sizeof(buffer), file)) {
        fclose(file);
        return;
    }

    fclose(file);

    char *start = strchr(buffer, '(');
    char *end = strrchr(buffer, ')');
    if (!start || !end)
        return;

    start++;
    size_t name_len = end - start;
    if (name_len >= sizeof(info->comm))
        name_len = sizeof(info->comm) - 1;
    memcpy(info->comm, start, name_len);
    info->comm[name_len] = '\0';

    char *rest = end + 1;
    long state = 0;
    long ppid = -1;
    long pgrp = -1;
    long session = -1;
    long tty_nr = -1;
    long tpgid = -1;
    long flags = 0;
    long minflt = 0;
    long cminflt = 0;
    long majflt = 0;
    long cmajflt = 0;
    long utime = 0;
    long stime = 0;
    long cutime = 0;
    long cstime = 0;
    long priority = 0;
    long nice = 0;
    long num_threads = 0;
    long itrealvalue = 0;
    long start_time = -1;

    if (sscanf(rest,
               " %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld",
               &state,
               &ppid,
               &pgrp,
               &session,
               &tty_nr,
               &tpgid,
               &flags,
               &minflt,
               &cminflt,
               &majflt,
               &cmajflt,
               &utime,
               &stime,
               &cutime,
               &cstime,
               &priority,
               &nice,
               &num_threads,
               &itrealvalue,
               &start_time) == 20) {
        if (info->ppid < 0)
            info->ppid = (pid_t)ppid;
        if (info->session_id < 0)
            info->session_id = (pid_t)session;
        if (info->tty_nr < 0)
            info->tty_nr = (pid_t)tty_nr;
        if (info->start_time < 0)
            info->start_time = start_time;
    }
}

static void read_exe(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/exe", info->pid);

    ssize_t n = readlink(path, info->exe, sizeof(info->exe) - 1);
    if (n >= 0)
        info->exe[n] = '\0';
}

static void read_cwd(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/cwd", info->pid);

    ssize_t n = readlink(path, info->cwd, sizeof(info->cwd) - 1);
    if (n >= 0)
        info->cwd[n] = '\0';
}

static void read_root(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/root", info->pid);

    ssize_t n = readlink(path, info->root, sizeof(info->root) - 1);
    if (n >= 0)
        info->root[n] = '\0';
}

static void read_cmdline(ProcessInfo *info)
{
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/cmdline", info->pid);

    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return;

    ssize_t n = read(fd, info->cmdline, sizeof(info->cmdline) - 1);
    close(fd);

    if (n <= 0)
        return;

    info->cmdline[n] = '\0';
    for (ssize_t i = 0; i < n - 1; i++) {
        if (info->cmdline[i] == '\0')
            info->cmdline[i] = ' ';
    }
}

int process_info_read(pid_t pid, ProcessInfo *info)
{
    process_info_reset(info, pid);

    if (pid <= 0)
        return -1;

    read_status(info);
    read_stat(info);
    read_exe(info);
    read_cwd(info);
    read_root(info);
    read_cmdline(info);

    return info->exe[0] || info->comm[0] || info->cmdline[0] || info->ppid >= 0 ? 0 : -1;
}
