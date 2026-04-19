import contextlib
import os
import time


if os.name == "nt":
    import msvcrt
else:
    import fcntl


class CloneTreeLock:
    """
    Advisory filesystem lock for the shared clones directory.

    Any TFRepair process that mutates files inside the same clones tree should
    acquire this lock first. This prevents two independent jobs from patching
    or validating the same clone set at the same time.
    """

    def __init__(self, clones_root: str, poll_interval_seconds: float = 1.0):
        self.clones_root = os.path.abspath(clones_root)
        self.poll_interval_seconds = poll_interval_seconds
        self.lock_path = os.path.join(self.clones_root, ".tfrepair.eval.lock")
        self._fh = None

    def acquire(self):
        os.makedirs(self.clones_root, exist_ok=True)
        self._fh = open(self.lock_path, "a+", encoding="utf-8")

        while True:
            try:
                if os.name == "nt":
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                print(
                    f"[LOCK] Waiting for clones lock: {self.lock_path} "
                    f"(another evaluation is using this clones directory)"
                )
                time.sleep(self.poll_interval_seconds)

        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(f"pid={os.getpid()}\n")
        self._fh.write(f"clones_root={self.clones_root}\n")
        self._fh.write(f"acquired_at={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        self._fh.flush()
        print(f"[LOCK] Acquired clones lock: {self.lock_path}")
        return self

    def release(self):
        if self._fh is None:
            return

        try:
            if os.name == "nt":
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
            print(f"[LOCK] Released clones lock: {self.lock_path}")

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


@contextlib.contextmanager
def clone_tree_lock(clones_root: str):
    lock = CloneTreeLock(clones_root)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()
