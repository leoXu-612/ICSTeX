// Installation-lifetime lock holder. No network, replacement, or signal sending.
// Sparkle 2.9.6 Autoupdate exits after final replacement and cleanup; its progress
// application launches asynchronously, so waiting for Autoupdate cannot deadlock
// a new application's startup lease.
#include <errno.h>
#include <fcntl.h>
#include <libproc.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/event.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static int identity(pid_t pid, unsigned long long *sec, unsigned long long *usec) {
    struct proc_bsdinfo info;
    int count = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info));
    if (count != sizeof(info)) return errno == ESRCH ? 1 : 2;
    *sec = info.pbi_start_tvsec;
    *usec = info.pbi_start_tvusec;
    return 0;
}

static int verify_bundle(const char *bundle) {
    pid_t child = fork();
    if (child == 0) {
        execl("/usr/bin/codesign", "codesign", "--verify", "--deep", "--strict", bundle, (char *)NULL);
        _exit(127);
    }
    if (child < 0) return 0;
    int status;
    while (waitpid(child, &status, 0) < 0) if (errno != EINTR) return 0;
    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

static int installers(pid_t *result, size_t capacity, const char *expected) {
    int bytes = proc_listpids(PROC_ALL_PIDS, 0, NULL, 0);
    if (bytes <= 0) return -1;
    size_t size = (size_t)bytes * 2;
    pid_t *pids = calloc(1, size);
    if (!pids) return -1;
    int used = proc_listpids(PROC_ALL_PIDS, 0, pids, (int)size);
    if (used <= 0 || (size_t)used >= size) { free(pids); return -1; }
    int found = 0;
    for (size_t i = 0; i < (size_t)used / sizeof(pid_t); i++) {
        char path[PROC_PIDPATHINFO_MAXSIZE] = {0};
        if (pids[i] <= 0) continue;
        if (proc_pidpath(pids[i], path, sizeof(path)) <= 0) {
            struct proc_bsdinfo info;
            if (proc_pidinfo(pids[i], PROC_PIDTBSDINFO, 0, &info, sizeof(info)) == sizeof(info) &&
                strcmp(info.pbi_comm, "Autoupdate") == 0) { free(pids); return -1; }
            continue;
        }
        const char *name = strrchr(path, '/');
        // Sparkle 2.9.6 runs Autoupdate IN the host framework (only its progress
        // app is copied into the cache). Bind to this exact executable path.
        // A preflight without a path conservatively refuses ANY live Autoupdate.
        if (name && strcmp(name, "/Autoupdate") == 0 && (!expected || strcmp(path, expected) == 0)) {
            if ((size_t)found == capacity) { free(pids); return -1; }
            result[found++] = pids[i];
        }
    }
    free(pids);
    return found;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--idle") == 0) {
        pid_t candidates[2];
        return installers(candidates, 2, NULL) == 0 ? 0 : 1;
    }
    if (argc == 5 && strcmp(argv[1], "--alive") == 0) {
        unsigned long long sec = 0, usec = 0;
        int state = identity((pid_t)strtol(argv[2], NULL, 10), &sec, &usec);
        if (state) return state;
        return sec == strtoull(argv[3], NULL, 10) && usec == strtoull(argv[4], NULL, 10) ? 0 : 1;
    }
    if (argc != 5) return 64;
    int gate = (int)strtol(argv[1], NULL, 10), use = (int)strtol(argv[2], NULL, 10);
    int channel = (int)strtol(argv[3], NULL, 10);
    struct stat st;
    if (gate < 3 || use < 3 || gate == use || fstat(gate, &st) || !S_ISREG(st.st_mode) ||
        st.st_nlink != 1 || st.st_size == 0 || fstat(use, &st) || !S_ISREG(st.st_mode) || st.st_nlink != 1 ||
        channel < 3 || channel == gate || channel == use || fstat(channel, &st) || !S_ISREG(st.st_mode)) return 65;
    // Do not keep the stdout/pipe reader's death as a reason to terminate.
    signal(SIGPIPE, SIG_IGN);
    int queue = kqueue();
    if (queue < 0) return 66;
    char path[PATH_MAX], expected[PATH_MAX];
    if (snprintf(path, sizeof(path), "%s/Contents/Frameworks/Sparkle.framework/Versions/B/Autoupdate", argv[4]) >= (int)sizeof(path) ||
        realpath(path, expected) == NULL) return 79;
    (void)write(STDOUT_FILENO, "READY\n", 6);
    int finished = 0;
    pid_t candidates[2];
    for (;;) {
        int count = installers(candidates, 2, expected);
        // Sparkle serializes installation by bundle identifier. Ambiguity is
        // fail-closed, not a guess about which process will replace this bundle.
        if (count < 0 || count > 1) return 67;
        if (count == 1) {
            unsigned long long sec = 0, usec = 0, after_sec = 0, after_usec = 0;
            if (identity(candidates[0], &sec, &usec)) return 68;
            struct kevent event;
            EV_SET(&event, (uintptr_t)candidates[0], EVFILT_PROC, EV_ADD | EV_ONESHOT, NOTE_EXIT, 0, NULL);
            if (kevent(queue, &event, 1, NULL, 0, NULL) != 0) return 69;
            if (identity(candidates[0], &after_sec, &after_usec) || sec != after_sec || usec != after_usec) return 70;
            char line[128];
            int length = snprintf(line, sizeof(line), "TRACKING %d %llu %llu\n", candidates[0], sec, usec);
            if (fstat(gate, &st) || pwrite(gate, line, (size_t)length, st.st_size) != length || fsync(gate)) return 71;
            (void)write(STDOUT_FILENO, "TRACKING\n", 9);
            for (;;) {
                int result = kevent(queue, NULL, 0, &event, 1, NULL);
                if (result < 0 && errno == EINTR) continue;
                if (result != 1 || !(event.fflags & NOTE_EXIT) || (event.flags & EV_ERROR)) return 72;
                break;
            }
            break;
        }
        if (finished) break; // Native cycle finished without any live installer.
        struct pollfd pipe = {.fd = STDIN_FILENO, .events = POLLIN | POLLHUP};
        int ready = poll(&pipe, 1, 50);
        if (ready < 0 && errno != EINTR) return 73;
        if (ready > 0) {
            char command[16] = {0};
            ssize_t bytes_read = read(STDIN_FILENO, command, sizeof(command) - 1);
            // Host death before installer registration is UNKNOWN. Keep the
            // journal for recovery, never release based on a fixed timeout.
            if (bytes_read <= 0) return 74;
            if (strcmp(command, "FINISH\n") != 0) return 75;
            finished = 1;
        }
    }
    if (!verify_bundle(argv[4])) return 76;
    if (ftruncate(gate, 0) || fsync(gate)) return 77;
    // These are shared open-file descriptions: downgrade the still-running
    // host's lease too, but never make it unprotected on a cancelled update.
    if (flock(use, LOCK_SH) || flock(gate, LOCK_UN) || flock(channel, LOCK_UN)) return 78;
    return 0;
}
