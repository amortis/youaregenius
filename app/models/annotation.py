from datetime import datetime, timezone

from app.extensions import db


class Annotation(db.Model):
    __tablename__ = "annotations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    translation_id = db.Column(db.Integer, db.ForeignKey("translations.id"), nullable=True)
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="annotations")
    track = db.relationship("Track", back_populates="annotations")
    translation = db.relationship("Translation", back_populates="annotations")

    @property
    def on_original(self) -> bool:
        return self.translation_id is None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Annotation {self.track_id} [{self.start_offset}:{self.end_offset}]>"