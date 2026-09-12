from datetime import datetime, timezone

from app.extensions import db


class Track(db.Model):
    __tablename__ = "tracks"
    __table_args__ = (
        db.UniqueConstraint("owner_id", "genius_id", name="uq_owner_genius"),
    )

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    genius_id = db.Column(db.String(32), nullable=False, index=True)
    title = db.Column(db.String(256), nullable=False)
    artist = db.Column(db.String(256), nullable=False)
    album = db.Column(db.String(256))
    cover_url = db.Column(db.String(512))
    source_url = db.Column(db.String(512))
    lyrics = db.Column(db.Text, nullable=False)
    structure = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    owner = db.relationship("User", back_populates="tracks")
    translations = db.relationship("Translation", back_populates="track", cascade="all, delete-orphan")
    annotations = db.relationship("Annotation", back_populates="track", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Track {self.title} — {self.artist} ({self.owner_id})>"