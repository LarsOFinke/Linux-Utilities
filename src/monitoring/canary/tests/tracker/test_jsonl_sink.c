#define _GNU_SOURCE
#include "jsonl_sink.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    char target_template[] = "/tmp/fs-tracker-target-XXXXXX";
    int target_fd = mkstemp(target_template);
    assert(target_fd >= 0);
    close(target_fd);

    char log_template[] = "/tmp/fs-tracker-log-XXXXXX";
    int log_fd = mkstemp(log_template);
    assert(log_fd >= 0);
    close(log_fd);

    assert(unlink(log_template) == 0);
    assert(link(target_template, log_template) == 0);

    JsonlSink sink;
    char err[256] = {0};
    assert(jsonl_sink_open(&sink, log_template, target_template, err, sizeof(err)) < 0);
    assert(sink.file == NULL);
    assert(strstr(err, "watched target") != NULL);

    assert(unlink(log_template) == 0);
    assert(unlink(target_template) == 0);

    char event_path[] = "/tmp/fs-tracker-event-XXXXXX";
    int event_fd = mkstemp(event_path);
    assert(event_fd >= 0);
    close(event_fd);
    unlink(event_path);

    FsEvent event = {0};
    event.timestamp.tv_sec = 1700000000;
    event.timestamp.tv_nsec = 123456789;
    event.mask = 1;
    snprintf(event.path, sizeof(event.path), "/tmp/test-canary.txt");

    ProcessInfo process = {0};
    process.pid = 1234;
    process.ppid = 1;
    process.uid = 1000;
    process.gid = 1000;
    process.euid = 1000;
    process.egid = 1000;
    process.session_id = 1234;
    process.start_time = 4567;
    process.tty_nr = 0;
    snprintf(process.exe, sizeof(process.exe), "/usr/bin/bash");
    snprintf(process.comm, sizeof(process.comm), "bash");
    snprintf(process.cmdline, sizeof(process.cmdline), "bash -lc echo hi");
    snprintf(process.cwd, sizeof(process.cwd), "/tmp");
    snprintf(process.root, sizeof(process.root), "/");

    char log_path[] = "/tmp/fs-tracker-metadata-XXXXXX";
    int log_fd_2 = mkstemp(log_path);
    assert(log_fd_2 >= 0);
    close(log_fd_2);
    unlink(log_path);

    char target_path_2[] = "/tmp/fs-tracker-target-other-XXXXXX";
    int target_fd_2 = mkstemp(target_path_2);
    assert(target_fd_2 >= 0);
    close(target_fd_2);

    JsonlSink sink2 = {0};
    assert(jsonl_sink_open(&sink2, log_path, target_path_2, err, sizeof(err)) >= 0);
    assert(jsonl_sink_write(&sink2, &event, &process, NULL) == 0);
    fclose(sink2.file);

    FILE *f = fopen(log_path, "r");
    assert(f != NULL);
    char buf[2048];
    assert(fgets(buf, sizeof(buf), f) != NULL);
    assert(strstr(buf, "\"comm\":\"bash\"") != NULL);
    assert(strstr(buf, "\"start_time\":4567") != NULL);
    assert(strstr(buf, "\"session_id\":1234") != NULL);
    assert(strstr(buf, "\"cwd\":\"/tmp\"") != NULL);
    fclose(f);
    unlink(log_path);
    unlink(target_path_2);

    return 0;
}
