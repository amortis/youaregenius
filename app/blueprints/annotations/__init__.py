from flask import Blueprint

bp = Blueprint("annotations", __name__)

from app.blueprints.annotations import routes  # noqa: E402, F401