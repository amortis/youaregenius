from flask import Blueprint

bp = Blueprint("translations", __name__)

from app.blueprints.translations import routes  # noqa: E402, F401