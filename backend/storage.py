from pathlib import Path
from threading import RLock
from tinydb import TinyDB
from tinydb.storages import JSONStorage


class ThreadSafeJSONStorage(JSONStorage):
    """Keep each seek/read or seek/write sequence on the shared handle together."""

    def __init__(self, *args, **kwargs):
        self._lock = RLock()
        super().__init__(*args, **kwargs)

    def read(self):
        with self._lock:
            return super().read()

    def write(self, data):
        with self._lock:
            return super().write(data)

    def close(self):
        with self._lock:
            return super().close()


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

db = TinyDB(DATA_DIR / "app.json", storage=ThreadSafeJSONStorage)
users_table = db.table("users")
profiles_table = db.table("profiles")
password_reset_tokens_table = db.table("password_reset_tokens")
candidates_table = db.table("candidates")
suppliers_table = db.table("suppliers")
