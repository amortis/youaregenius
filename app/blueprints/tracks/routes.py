from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.tracks import bp
from app.blueprints.tracks.forms import SearchForm
from app.extensions import db
from app.models import Annotation, Track, Translation
from app.services import genius
from app.services.structures import structure_to_text


@bp.get("/tracks/my")
@login_required
def my_tracks():
    tracks = db.session.scalars(
        db.select(Track)
        .where(Track.owner_id == current_user.id)
        .order_by(Track.created_at.desc())
    ).all()
    return render_template("tracks/my_tracks.html", tracks=tracks)


@bp.get("/tracks/all")
@login_required
def all_tracks():
    rows = db.session.execute(
        db.select(Annotation, Track)
        .join(Track, Annotation.track_id == Track.id)
        .order_by(Annotation.created_at.desc())
    ).all()
    return render_template("tracks/all_tracks.html", rows=rows)


@bp.route("/tracks/search", methods=["GET", "POST"])
@login_required
def search():
    form = SearchForm()
    results = []
    is_partial = request.headers.get("HX-Request") == "true"
    if form.validate_on_submit():
        results = genius.search(
            form.q.data, user_agent=current_app.config["GENIUS_USER_AGENT"]
        )
        if is_partial:
            return render_template("tracks/_search_results.html", results=results)
        return render_template("tracks/search.html", form=form, results=results)

    template = "tracks/_results_shell.html" if is_partial else "tracks/search.html"
    return render_template(template, form=form, results=results)


@bp.post("/tracks/import/<genius_id>")
@login_required
def import_track(genius_id: str):
    track = db.session.scalar(
        db.select(Track).where(
            Track.genius_id == genius_id, Track.owner_id == current_user.id
        )
    )
    if track is None:
        try:
            data = genius.scrape_track(
                genius_id, user_agent=current_app.config["GENIUS_USER_AGENT"]
            )
        except genius.GeniusError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("tracks.search"))
        track = Track(
            owner_id=current_user.id,
            genius_id=data["genius_id"],
            title=data["title"],
            artist=data["artist"],
            album=data.get("album"),
            cover_url=data.get("cover_url"),
            source_url=data.get("source_url"),
            lyrics=data["lyrics"],
            structure=data["structure"],
        )
        db.session.add(track)
    db.session.commit()

    flash(f"«{track.title}» добавлен в вашу коллекцию.", "success")
    return redirect(url_for("tracks.track_detail", track_id=track.id))


@bp.get("/tracks/<int:track_id>")
@login_required
def track_detail(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    translation = db.session.scalar(
        db.select(Translation).where(
            Translation.track_id == track_id, Translation.user_id == current_user.id
        )
    )
    annotations = db.session.scalars(
        db.select(Annotation)
        .where(Annotation.track_id == track_id)
        .order_by(Annotation.start_offset)
    ).all()

    from app.services.lines import attach_annotations, build_line_map

    original_annotations = [a for a in annotations if a.on_original]
    translation_annotations = []
    if translation is not None:
        translation_annotations = [
            a for a in annotations if a.translation_id == translation.id
        ]

    from app.services.lines import build_view_blocks, build_view_rows

    orig_blocks = attach_annotations(build_line_map(track.structure), original_annotations)
    orig_rows = build_view_blocks(orig_blocks)
    trans_rows = None
    split_rows = None
    if translation is not None:
        trans_blocks = attach_annotations(
            build_line_map(translation.structure), translation_annotations
        )
        trans_rows = build_view_blocks(trans_blocks)
        split_rows = build_view_rows(orig_blocks, trans_blocks)

    return render_template(
        "tracks/track_detail.html",
        track=track,
        translation=translation,
        annotations=annotations,
        orig_rows=orig_rows,
        trans_rows=trans_rows,
        split_rows=split_rows,
        is_owner=track.owner_id == current_user.id,
    )


def _require_owner(track: Track) -> None:
    if track.owner_id != current_user.id:
        abort(403)


@bp.get("/tracks/<int:track_id>/editor")
@login_required
def editor(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)
    return render_template("tracks/editor.html", track=track)


@bp.post("/tracks/<int:track_id>/refresh")
@login_required
def refresh_lyrics(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)
    try:
        data = genius.scrape_track(
            track.genius_id, user_agent=current_app.config["GENIUS_USER_AGENT"]
        )
    except genius.GeniusError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("tracks.track_detail", track_id=track_id))

    track.title = data["title"]
    track.artist = data["artist"]
    track.album = data.get("album")
    track.cover_url = data.get("cover_url")
    track.source_url = data.get("source_url")
    track.lyrics = data["lyrics"]
    track.structure = data["structure"]
    db.session.commit()
    flash(
        "Текст обновлён с Genius. Внимание: оффсеты существующих аннотаций "
        "могут не совпадать с новым текстом.",
        "warning",
    )
    return redirect(url_for("tracks.track_detail", track_id=track_id))


@bp.route("/tracks/<int:track_id>/edit-original", methods=["GET", "POST"])
@login_required
def edit_original(track_id: int):
    track = db.session.get(Track, track_id)
    if track is None:
        abort(404)
    _require_owner(track)

    if request.method == "POST":
        structure = []
        for i, seg in enumerate(track.structure):
            heading = request.form.get(f"heading_{i}") or None
            n = len(seg.get("lines", []))
            lines = request.form.getlist(f"line_{i}")[:n]
            lines = [line.strip() for line in lines if line.strip()]
            if lines:
                structure.append({"heading": heading, "lines": lines})
        track.structure = structure
        track.lyrics = structure_to_text(structure)
        db.session.commit()
        flash(
            "Оригинал обновлён, пустые строки удалены. Внимание: оффсеты "
            "существующих аннотаций могут не совпадать с новым текстом.",
            "warning",
        )
        return redirect(url_for("tracks.track_detail", track_id=track_id))

    return render_template("tracks/edit_original.html", track=track)