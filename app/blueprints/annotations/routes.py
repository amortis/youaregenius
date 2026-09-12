from flask import abort, flash, render_template, request
from flask_login import current_user, login_required

from app.blueprints.annotations import bp
from app.extensions import db
from app.models import Annotation, Track, Translation
from app.services.annotations import AnnotationError, build_excerpt, validate_offsets


def _annotations_for_user(track_id: int):
    return (
        db.select(Annotation)
        .where(Annotation.track_id == track_id)
        .order_by(Annotation.start_offset)
    )


def _render_list(track_id: int):
    annotations = db.session.scalars(_annotations_for_user(track_id)).all()
    return render_template("annotations/_annotations.html", annotations=annotations)


@bp.post("/tracks/<int:track_id>/annotations")
@login_required
def create(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    if track.owner_id != current_user.id:
        abort(403)

    content = (request.form.get("content") or "").strip()
    if not content:
        return _render_list(track_id)

    translation_id = request.form.get("translation_id") or None
    start = int(request.form["start"])
    end = int(request.form["end"])

    if translation_id:
        translation = db.session.get(Translation, int(translation_id))
        if translation is None or translation.user_id != current_user.id:
            abort(403)
        text = translation.content
    else:
        text = track.lyrics

    try:
        validate_offsets(text, start, end)
        excerpt = build_excerpt(text, start, end)
    except AnnotationError as exc:
        flash(str(exc), "danger")
        return _render_list(track_id)

    annotation = Annotation(
        user_id=current_user.id,
        track_id=track.id,
        translation_id=int(translation_id) if translation_id else None,
        start_offset=start,
        end_offset=end,
        content=content,
        excerpt=excerpt,
    )
    db.session.add(annotation)
    db.session.commit()
    return _render_list(track_id)


@bp.post("/annotations/<int:annotation_id>/update")
@login_required
def update(annotation_id: int):
    annotation = db.session.get(Annotation, annotation_id)
    if annotation is None:
        abort(404)
    if annotation.user_id != current_user.id:
        abort(403)

    content = (request.form.get("content") or "").strip()
    if content:
        annotation.content = content
        db.session.commit()
    return _render_list(annotation.track_id)


@bp.post("/annotations/<int:annotation_id>/delete")
@login_required
def delete(annotation_id: int):
    annotation = db.session.get(Annotation, annotation_id)
    if annotation is None:
        abort(404)
    if annotation.user_id != current_user.id:
        abort(403)

    track_id = annotation.track_id
    db.session.delete(annotation)
    db.session.commit()
    return _render_list(track_id)