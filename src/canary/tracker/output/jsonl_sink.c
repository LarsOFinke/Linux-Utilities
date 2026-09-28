#define _POSIX_C_SOURCE 200809L
#include "jsonl_sink.h"
#include "event_names.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void write_json_string(FILE *out, const char *text)
{
    fputc('"', out);

    for (const unsigned char *p = (const unsigned char *)text; *p; p++) {
        switch (*p) {
        case '"': fputs("\\\"", out); break;
        case '\\': fputs("\\\\", out); break;
        case '\b': fputs("\\b", out); break;
        case '\f': fputs("\\f", out); break;
        case '\n': fputs("\\n", out); break;
        case '\r': fputs("\\r", out); break;
        case '\t': fputs("\\t", out); break;
        default:
            if (*p < 0x20)
                fprintf(out, "\\u%04x", *p);
            else
                fputc(*p, out);
        }
    }

    fputc('"', out);
}

static void write_timestamp(FILE *out, const struct timespec *timestamp)
{
    struct tm tm;
    gmtime_r(&timestamp->tv_sec, &tm);

    char base[32];
    strftime(base, sizeof(base), "%Y-%m-%dT%H:%M:%S", &tm);
    fprintf(out, "\"%s.%09ldZ\"", base, timestamp->tv_nsec);
}

static void write_event_names(FILE *out, uint64_t mask)
{
    const char *names[8];
    size_t count = fs_event_mask_to_names(mask, names, sizeof(names) / sizeof(names[0]));

    fputc('[', out);
    for (size_t i = 0; i < count; i++) {
        if (i)
            fputc(',', out);
        write_json_string(out, names[i]);
    }
    fputc(']', out);
}

static void write_process(FILE *out, const ProcessInfo *info)
{
    if (!info || info->pid <= 0) {
        fputs("null", out);
        return;
    }

    fputs("{\"pid\":", out);
    fprintf(out, "%d", info->pid);
    fputs(",\"ppid\":", out);
    fprintf(out, "%d", info->ppid);
    fputs(",\"uid\":", out);
    if (info->uid == (uid_t)-1)
        fputs("null", out);
    else
        fprintf(out, "%u", (unsigned)info->uid);
    fputs(",\"euid\":", out);
    if (info->euid == (uid_t)-1)
        fputs("null", out);
    else
        fprintf(out, "%u", (unsigned)info->euid);
    fputs(",\"gid\":", out);
    if (info->gid == (gid_t)-1)
        fputs("null", out);
    else
        fprintf(out, "%u", (unsigned)info->gid);
    fputs(",\"egid\":", out);
    if (info->egid == (gid_t)-1)
        fputs("null", out);
    else
        fprintf(out, "%u", (unsigned)info->egid);
    fputs(",\"session_id\":", out);
    if (info->session_id < 0)
        fputs("null", out);
    else
        fprintf(out, "%d", info->session_id);
    fputs(",\"tty_nr\":", out);
    if (info->tty_nr < 0)
        fputs("null", out);
    else
        fprintf(out, "%d", info->tty_nr);
    fputs(",\"start_time\":", out);
    if (info->start_time < 0)
        fputs("null", out);
    else
        fprintf(out, "%ld", info->start_time);
    fputs(",\"exe\":", out);
    write_json_string(out, info->exe);
    fputs(",\"comm\":", out);
    write_json_string(out, info->comm);
    fputs(",\"cmdline\":", out);
    write_json_string(out, info->cmdline);
    fputs(",\"cwd\":", out);
    write_json_string(out, info->cwd);
    fputs(",\"root\":", out);
    write_json_string(out, info->root);
    fputc('}', out);
}

int jsonl_sink_open(JsonlSink *sink, const char *path, const char *target_path, char *err, size_t err_size)
{
    sink->file = NULL;
    sink->file = fopen(path, "a");
    if (!sink->file) {
        snprintf(err, err_size, "cannot open log '%s': %s", path, strerror(errno));
        return -1;
    }

    struct stat target_stat;
    struct stat log_stat;
    if (stat(target_path, &target_stat) < 0 || fstat(fileno(sink->file), &log_stat) < 0) {
        snprintf(err, err_size, "cannot verify log '%s' is separate from target '%s': %s",
                 path, target_path, strerror(errno));
        fclose(sink->file);
        sink->file = NULL;
        return -1;
    }

    if (target_stat.st_dev == log_stat.st_dev && target_stat.st_ino == log_stat.st_ino) {
        snprintf(err, err_size, "log '%s' refers to the watched target '%s'",
                 path, target_path);
        fclose(sink->file);
        sink->file = NULL;
        return -1;
    }

    setvbuf(sink->file, NULL, _IOLBF, 0);
    return 0;
}

int jsonl_sink_write(JsonlSink *sink, const FsEvent *event, const ProcessInfo *process, const ProcessInfo *parent)
{
    FILE *out = sink->file;

    fputs("{\"ts\":", out);
    write_timestamp(out, &event->timestamp);
    fputs(",\"path\":", out);
    write_json_string(out, event->path);
    fputs(",\"mask\":", out);
    fprintf(out, "%llu", (unsigned long long)event->mask);
    fputs(",\"events\":", out);
    write_event_names(out, event->mask);
    fputs(",\"process\":", out);
    write_process(out, process);
    fputs(",\"parent\":", out);
    write_process(out, parent);
    fputs("}\n", out);

    return ferror(out) ? -1 : 0;
}

void jsonl_sink_close(JsonlSink *sink)
{
    if (sink->file)
        fclose(sink->file);
    sink->file = NULL;
}
