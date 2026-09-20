"""Environment-driven configuration.

Production deliberately has no fallback secret. The old project shipped
SECRET_KEY = "dev-carelink-secret-change-me" as a default, which meant anyone
who read the source could forge a signed session cookie for any user, including
the admin. ProductionConfig.init_app now refuses to start without real values.
"""

import os


def _origins_from_env(default: str) -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGINS", default)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # SSLCommerz sandbox. Never commit real values - use .env locally and
    # GitHub Actions secrets in CI.
    SSLCOMMERZ_STORE_ID = os.environ.get("SSLCOMMERZ_STORE_ID")
    SSLCOMMERZ_STORE_PASSWORD = os.environ.get("SSLCOMMERZ_STORE_PASSWORD")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

    @staticmethod
    def init_app(app):
        """Hook for per-environment validation."""


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-never-deploy-this")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///caresphere-dev.db")
    # Pick ONE host and use it everywhere. 127.0.0.1 and localhost are
    # different sites to the browser, so mixing them silently drops the
    # session cookie on cross-origin fetches under SameSite=Lax.
    FRONTEND_ORIGINS = _origins_from_env("http://127.0.0.1:5500")


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "testing-key-not-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    FRONTEND_ORIGINS = ["http://127.0.0.1:5500"]


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    FRONTEND_ORIGINS = _origins_from_env("")

    @staticmethod
    def init_app(app):
        missing = [
            name for name in ("SECRET_KEY", "SQLALCHEMY_DATABASE_URI") if not app.config.get(name)
        ]
        if missing:
            raise RuntimeError("Refusing to start in production without: " + ", ".join(missing))
        if not app.config["FRONTEND_ORIGINS"]:
            raise RuntimeError("FRONTEND_ORIGINS must be set in production")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
