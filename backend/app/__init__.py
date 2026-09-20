"""CareSphere application factory."""

import os

from flask import Flask, jsonify

from .cli import register_cli
from .config import config_by_name
from .extensions import cors, db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a CareSphere Flask application."""
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    config_class = config_by_name[config_name]

    app = Flask(__name__)
    app.config.from_object(config_class)
    config_class.init_app(app)

    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    register_cli(app)

    @app.get("/api/health")
    def health():
        """Liveness probe. Used by CI and by the deploy platform."""
        return jsonify({"status": "ok", "service": "caresphere-api"})

    return app


def _register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        origins=app.config["FRONTEND_ORIGINS"],
        supports_credentials=True,
        allow_headers=["Content-Type"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    # Importing the package registers every model with SQLAlchemy's metadata,
    # which Flask-Migrate needs in order to autogenerate migrations.
    from . import models  # noqa: F401


def _register_blueprints(app: Flask) -> None:
    """Blueprints are registered here as each module is ported.

    Porting schedule lives in docs/PORTING.md. Uncomment a line only in the
    pull request that actually ports that module, so the diff stays readable.
    """
    from .blueprints.admin import admin_bp
    from .blueprints.auth import auth_bp
    from .blueprints.doctors import doctors_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(admin_bp)

    # Week 3 - Shuvo  from .blueprints.appointments import appointments_bp
    # Week 4 - Shuvo  from .blueprints.payments import payments_bp
    # Week 5 - Shuvo  from .blueprints.chat import chat_bp
    # Week 6 - Shuvo  from .blueprints.emergency import emergency_bp
    # Week 4 - Ifti   from .blueprints.donors import donors_bp
    # Week 6 - Ifti   from .blueprints.ambulance import ambulance_bp
    # Week 5 - Jit    from .blueprints.prescriptions import prescriptions_bp
    # Week 7 - Jit    from .blueprints.reminders import reminders_bp


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500
