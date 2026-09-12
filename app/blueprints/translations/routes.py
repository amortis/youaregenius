from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.blueprints.translations import bp
from app.extensions import db
from app.models import Track, Translation
from app.services import translation as translation_svc
from app.services.structures import structure_to_text


def _get_owned_translation(track_id: int) -> Translation | None:
    return db.session.scalar(
        db.select(Translation).where(
            Translation.track_id == track_id,
            Translation.user_id == current_user.id,
            Translation.lang == "ru",
        )
    )


def _require_owner(track: Track) -> None:
    if track.owner_id != current_user.id:
        abort(403)


@bp.get("/tracks/<int:track_id>/translate")
@login_required
def translate_page(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    translation = _get_owned_translation(track_id)
    return render_template(
        "translations/translate.html", track=track, translation=translation
    )


@bp.post("/tracks/<int:track_id>/translate/generate")
@login_required
def generate(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)

    api_key = current_app.config["DEEPL_API_KEY"]
    provider = translation_svc.get_provider(api_key)
    if provider is None:
        flash("API-ключ DeepL не настроен. Добавьте DEEPL_API_KEY в .env", "danger")
        return redirect(url_for("translations.translate_page", track_id=track_id))

    translation = _get_owned_translation(track_id)
    try:
        structure = _translate_structure(track, provider)
        if translation is None:
            translation = Translation(
                user_id=current_user.id,
                track_id=track.id,
                lang="ru",
                structure=structure,
                content=structure_to_text(structure),
                source="auto",
            )
            db.session.add(translation)
        else:
            # перегенерация: пересобираем структуру и текст заново
            translation.structure = structure
            translation.content = structure_to_text(structure)
            translation.source = "auto"
        db.session.commit()
    except translation_svc.TranslationError as exc:
        flash(f"Не удалось перевести: {exc}", "danger")
        return redirect(url_for("translations.translate_page", track_id=track_id))

    return redirect(url_for("translations.translate_page", track_id=track_id))


def _translate_structure(track: Track, provider) -> list[dict]:
    from app.services.genius import GeniusError

    result = []
    try:
        for seg in track.structure:
            translated = provider.translate_lines(seg.get("lines", []))
            result.append({"heading": seg.get("heading"), "lines": translated})
    except Exception as exc:  # noqa: BLE001
        raise translation_svc.TranslationError(str(exc)) from exc
    return result


@bp.post("/tracks/<int:track_id>/translate/create-manual")
@login_required
def create_manual(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)

    if _get_owned_translation(track_id) is None:
        structure = [
            {"heading": seg.get("heading"), "lines": ["" for _ in seg.get("lines", [])]}
            for seg in track.structure
        ]
        translation = Translation(
            user_id=current_user.id,
            track_id=track.id,
            lang="ru",
            structure=structure,
            content=structure_to_text(structure),
            source="manual",
        )
        db.session.add(translation)
        db.session.commit()
    return redirect(url_for("translations.translate_page", track_id=track_id))


@bp.post("/tracks/<int:track_id>/translate/save")
@login_required
def save(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)

    translation = _get_owned_translation(track_id)
    if translation is None:
        flash("Сначала сгенерируйте перевод.", "warning")
        return redirect(url_for("translations.translate_page", track_id=track_id))

    structure = []
    blocks = request.form.getlist("block_index")
    for block_idx in blocks:
        heading = request.form.get(f"heading_{block_idx}") or None
        lines = request.form.getlist(f"line_{block_idx}")
        structure.append({"heading": heading, "lines": lines})

    translation.structure = structure
    translation.content = structure_to_text(structure)
    translation.source = "manual"
    db.session.commit()
    flash("Перевод сохранён.", "success")
    return redirect(url_for("translations.translate_page", track_id=track_id))