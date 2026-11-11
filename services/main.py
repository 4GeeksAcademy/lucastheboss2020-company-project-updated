from backend.main import app

from services.database import create_db_and_tables
from services.incidents.api import router as incidents_router
from services.reporting.router import router as reporting_router
from services.routers.inventory import router as inventory_router
from services.routers.knowledge import router as knowledge_router
from services.routers.telemetry import router as telemetry_router
from services.suppliers.api import router as suppliers_router
from services.task_api import router as task_api_router

app.include_router(inventory_router)
app.include_router(knowledge_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
app.include_router(telemetry_router)
app.include_router(reporting_router)
app.include_router(task_api_router)
app.router.on_startup.append(create_db_and_tables)
