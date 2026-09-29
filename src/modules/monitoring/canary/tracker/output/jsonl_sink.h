#ifndef FSTRACKER_JSONL_SINK_H
#define FSTRACKER_JSONL_SINK_H

#include "event.h"
#include "proc_info.h"

#include <stddef.h>
#include <stdio.h>

typedef struct {
    FILE *file;
} JsonlSink;

int jsonl_sink_open(JsonlSink *sink, const char *path, const char *target_path, char *err, size_t err_size);
int jsonl_sink_write(JsonlSink *sink, const FsEvent *event, const ProcessInfo *process, const ProcessInfo *parent);
void jsonl_sink_close(JsonlSink *sink);

#endif
