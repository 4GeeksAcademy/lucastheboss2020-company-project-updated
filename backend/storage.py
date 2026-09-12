from pathlib import Path
from tinydb import TinyDB


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

db = TinyDB(DATA_DIR / "app.json")
users_table = db.table("users")
profiles_table = db.table("profiles")
candidates_table = db.table("candidates")
