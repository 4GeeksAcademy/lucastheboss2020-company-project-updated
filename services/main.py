from backend.main import app

from services.database import create_db_and_tables
from services.routers.inventory import router as inventory_router

app.include_router(inventory_router)
app.router.on_startup.append(create_db_and_tables)
