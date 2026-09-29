#include "event_names.h"

#include <sys/fanotify.h>

size_t fs_event_mask_to_names(uint64_t mask, const char **names, size_t capacity)
{
    size_t count = 0;

#define ADD_EVENT(bit, label)                  \
    do {                                       \
        if ((mask & (bit)) && count < capacity) \
            names[count++] = (label);          \
    } while (0)

    ADD_EVENT(FAN_OPEN, "open");
    ADD_EVENT(FAN_ACCESS, "access");
    ADD_EVENT(FAN_MODIFY, "modify");
#ifdef FAN_OPEN_EXEC
    ADD_EVENT(FAN_OPEN_EXEC, "open_exec");
#endif
    ADD_EVENT(FAN_CLOSE_WRITE, "close_write");
    ADD_EVENT(FAN_CLOSE_NOWRITE, "close_nowrite");
    ADD_EVENT(FAN_Q_OVERFLOW, "queue_overflow");

#undef ADD_EVENT

    return count;
}
