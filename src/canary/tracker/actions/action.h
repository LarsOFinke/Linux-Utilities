#ifndef FSTRACKER_ACTION_H
#define FSTRACKER_ACTION_H

#include "event.h"

#include <stddef.h>

int action_run(const char *path, const FsEvent *event, char *err, size_t err_size);

#endif