#include "event_names.h"

#include <assert.h>
#include <string.h>
#include <sys/fanotify.h>

int main(void)
{
    const char *names[8] = {0};
    size_t count = fs_event_mask_to_names(FAN_OPEN | FAN_ACCESS, names, 8);

    assert(count == 2);
    assert(strcmp(names[0], "open") == 0);
    assert(strcmp(names[1], "access") == 0);

    return 0;
}
