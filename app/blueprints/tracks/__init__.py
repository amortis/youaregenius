from flask import Blueprint

bp = Blueprint("tracks", __name__)

from app.blueprints.tracks import routes  # noqa: E402, F401