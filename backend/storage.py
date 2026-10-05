from pathlib import Path
from tinydb import TinyDB


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

db = TinyDB(DATA_DIR / "app.json")
users_table = db.table("users")
profiles_table = db.table("profiles")
password_reset_tokens_table = db.table("password_reset_tokens")
candidates_table = db.table("candidates")
suppliers_table = db.table("suppliers")