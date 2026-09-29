#ifndef FSTRACKER_PROC_INFO_H
#define FSTRACKER_PROC_INFO_H

#include <linux/limits.h>
#include <stddef.h>
#include <sys/types.h>

typedef struct {
    pid_t pid;
    pid_t ppid;
    uid_t uid;
    uid_t euid;
    gid_t gid;
    gid_t egid;
    pid_t session_id;
    pid_t tty_nr;
    long start_time;
    char exe[PATH_MAX];
    char comm[256];
    char cmdline[4096];
    char cwd[PATH_MAX];
    char root[PATH_MAX];
} ProcessInfo;

int process_info_read(pid_t pid, ProcessInfo *info);

#endif
