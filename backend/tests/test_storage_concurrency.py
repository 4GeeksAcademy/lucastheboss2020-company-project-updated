from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

from backend.storage import ThreadSafeJSONStorage


class YieldingHandle:
    """Make the shared cursor race reproducible between seek and read/write."""

    def __init__(self, handle):
        self.handle = handle

    def __getattr__(self, name):
        return getattr(self.handle, name)

    def seek(self, *args):
        result = self.handle.seek(*args)
        sleep(0.0001)
        return result


def test_parallel_user_reads_and_writes_keep_complete_json(tmp_path):
    storage = ThreadSafeJSONStorage(tmp_path / "app.json")
    payload = {"users": {"1": {"id": "test-user", "active": True}}}
    storage.write(payload)
    storage._handle = YieldingHandle(storage._handle)
    start = Barrier(9)

    def reader():
        start.wait()
        for _ in range(40):
            assert storage.read() == payload

    def writer():
        start.wait()
        for _ in range(40):
            storage.write(payload)

    try:
        with ThreadPoolExecutor(max_workers=9) as pool:
            jobs = [pool.submit(reader) for _ in range(8)] + [pool.submit(writer)]
            for job in jobs:
                job.result(timeout=15)
        assert storage.read() == payload
    finally:
        storage.close()
