"""Guard all installed entry modes before importing application workflows."""
from app.core.update_install_guard import enter_installed_application

enter_installed_application()
