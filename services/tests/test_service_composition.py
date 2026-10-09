from services.incidents.api import app as incidents_app
from services.main import app as combined_app
from services.suppliers.api import app as suppliers_app


def operations(app):
    return {
        (path, method.upper())
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }


def test_combined_api_registers_inventory_supplier_and_incident_routes():
    registered = operations(combined_app)

    assert {
        ("/inventory/products", "GET"),
        ("/suppliers", "GET"),
        ("/incidents/analyses", "GET"),
        ("/api/incidents", "GET"),
    } <= registered


def test_standalone_supplier_and_incident_apps_keep_their_route_contracts():
    assert ("/suppliers", "GET") in operations(suppliers_app)
    incident_routes = operations(incidents_app)
    assert ("/incidents/analyses", "GET") in incident_routes
    assert ("/api/incidents", "GET") in incident_routes