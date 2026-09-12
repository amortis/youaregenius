from flask import Flask, redirect, render_template, url_for

from app.config import config_map
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name: str = "dev") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    if config_name == "prod":
        from app.config import validate_config

        validate_config(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.services.lines import (
    annotation_cards,
    annotation_payload,
    annotation_tip,
    marked_line,
)

    app.jinja_env.globals["marked_line"] = marked_line
    app.jinja_env.globals["annotation_tip"] = annotation_tip
    app.jinja_env.globals["annotation_cards"] = annotation_cards
    app.jinja_env.globals["annotation_payload"] = annotation_payload

    @app.template_filter("headline")
    def headline(value):
        """'[Verse 1]' -> 'Verse 1' (заголовок без квадратных скобок)."""
        if value and value.startswith("[") and value.endswith("]"):
            return value[1:-1].strip()
        return value

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from app.blueprints.annotations import bp as annotations_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.tracks import bp as tracks_bp
    from app.blueprints.translations import bp as translations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tracks_bp)
    app.register_blueprint(annotations_bp)
    app.register_blueprint(translations_bp)

    @app.route("/")
    def index():
        return redirect(url_for("tracks.my_tracks"))

    return app