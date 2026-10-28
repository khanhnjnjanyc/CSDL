from backend.routes.overview import overview_bp
from backend.routes.patients import patients_bp
from backend.routes.visits_episodes import visits_episodes_bp
from backend.routes.prescriptions import prescriptions_bp
from backend.routes.staff_catalog import staff_catalog_bp
from backend.routes.reports import reports_bp

all_blueprints = [
    overview_bp,
    patients_bp,
    visits_episodes_bp,
    prescriptions_bp,
    staff_catalog_bp,
    reports_bp,
]