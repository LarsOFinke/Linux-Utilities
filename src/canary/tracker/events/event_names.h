#ifndef FSTRACKER_EVENT_NAMES_H
#define FSTRACKER_EVENT_NAMES_H

#include <stddef.h>
#include <stdint.h>

size_t fs_event_mask_to_names(uint64_t mask, const char **names, size_t capacity);

#endif
