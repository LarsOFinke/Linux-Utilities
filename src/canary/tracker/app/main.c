#include "config.h"
#include "action.h"
#include "event.h"
#include "fanotify_source.h"
#include "jsonl_sink.h"
#include "proc_info.h"

#include <stdio.h>
#include <string.h>
#include <sys/fanotify.h>

int main(int argc, char **argv)
{
    TrackerConfig config;
    char err[512] = {0};

    int parse_result = tracker_config_load(&config, argc, argv, err, sizeof(err));
    if (parse_result > 0) {
        tracker_config_print_usage(argv[0]);
        return 0;
    }
    if (parse_result < 0) {
        fprintf(stderr, "config: %s\n", err);
        tracker_config_print_usage(argv[0]);
        return 2;
    }

    FanotifySource source;
    if (fanotify_source_open(&source, config.target_path, err, sizeof(err)) < 0) {
        fprintf(stderr, "%s\n", err);
        fprintf(stderr, "Hint: run as root or with the capabilities required by your kernel.\n");
        return 1;
    }

    JsonlSink sink;
    if (jsonl_sink_open(&sink, config.log_path, config.target_path, err, sizeof(err)) < 0) {
        fprintf(stderr, "%s\n", err);
        fanotify_source_close(&source);
        return 1;
    }

    fprintf(stderr, "tracking %s -> %s\n", config.target_path, config.log_path);

    for (;;) {
        FsEvent event;
        if (fanotify_source_next(&source, &event, err, sizeof(err)) < 0) {
            fprintf(stderr, "%s\n", err);
            break;
        }

        if (!event.path[0])
            snprintf(event.path, sizeof(event.path), "%s", config.target_path);

        ProcessInfo process = {0};
        ProcessInfo parent = {0};

        if (!(event.mask & FAN_Q_OVERFLOW) && event.pid > 0 &&
            process_info_read(event.pid, &process) == 0) {
            if (process.ppid > 0)
                process_info_read(process.ppid, &parent);
        }

        if (jsonl_sink_write(&sink, &event,
                             process.pid > 0 ? &process : NULL,
                             parent.pid > 0 ? &parent : NULL) < 0) {
            fprintf(stderr, "failed to write JSONL log\n");
            break;
        }

        if (config.action_path[0]) {
            char action_err[512] = {0};
            if (action_run(config.action_path, &event, action_err, sizeof(action_err)) < 0)
                fprintf(stderr, "%s\n", action_err);
        }
    }

    jsonl_sink_close(&sink);
    fanotify_source_close(&source);
    return 1;
}
