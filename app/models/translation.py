from datetime import datetime, timezone

from app.extensions import db


class Translation(db.Model):
    __tablename__ = "translations"
    __table_args__ = (
        db.UniqueConstraint("user_id", "track_id", "lang", name="uq_user_track_lang"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    lang = db.Column(db.String(16), nullable=False, default="ru")
    content = db.Column(db.Text, nullable=False)
    structure = db.Column(db.JSON, nullable=False, default=list)
    source = db.Column(db.String(16), nullable=False, default="auto")  # auto | manual
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="translations")
    track = db.relationship("Track", back_populates="translations")
    annotations = db.relationship("Annotation", back_populates="translation")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Translation {self.track_id} {self.lang} by {self.user_id}>"