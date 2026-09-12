import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env(name: str, default: str) -> str:
    """Значение переменной окружения или дефолт (пустая строка = не задано)."""
    value = os.environ.get(name)
    return value if value else default


class Config:
    SECRET_KEY = _env("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEEPL_API_KEY = _env("DEEPL_API_KEY", "")
    GENIUS_USER_AGENT = _env(
        "GENIUS_USER_AGENT",
        "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    )


class DevConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _env(
        "DEV_DATABASE_URI",
        f"sqlite:///{os.path.join(BASE_DIR, '..', 'youaregenius_dev.db')}",
    )


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProdConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URI")


def validate_config(app) -> None:
    config = app.config
    if not config["SQLALCHEMY_DATABASE_URI"]:
        raise RuntimeError(
            "DATABASE_URI must be set (e.g. DATABASE_URI=postgresql+psycopg2://...)"
        )


config_map = {
    "dev": DevConfig,
    "test": TestConfig,
    "prod": ProdConfig,
}