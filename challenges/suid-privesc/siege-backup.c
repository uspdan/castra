#include <stdlib.h>
#include <unistd.h>

int main() {
    setuid(0);
    setgid(0);
    system("tar czf /tmp/backup.tar.gz /opt/data");
    return 0;
}
