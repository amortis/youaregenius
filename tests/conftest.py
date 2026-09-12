import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    application = create_app("test")
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def register_user(client, username="testuser", password="secret1"):
    client.post(
        "/auth/register",
        data={"username": username, "password": password, "confirm": password},
    )
    return {"username": username, "password": password}


SAMPLE_TRACK = {
    "genius_id": "3781",
    "title": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "cover_url": "https://example.com/cover.png",
    "source_url": "https://genius.com/songs/3781",
    "structure": [
        {"heading": "[Verse 1]", "lines": ["Is this the real life?", "Is this just fantasy?"]},
        {"heading": None, "lines": ["Caught in a landslide", "No escape from reality"]},
    ],
    "lyrics": "[Verse 1]\nIs this the real life?\nIs this just fantasy?\n\nCaught in a landslide\nNo escape from reality",
}


@pytest.fixture()
def mock_genius(app, monkeypatch):
    from app.services import genius

    def fake_scrape(genius_id, user_agent=None):
        return {**SAMPLE_TRACK, "genius_id": genius_id}

    monkeypatch.setattr(genius, "scrape_track", fake_scrape)
    return genius


@pytest.fixture()
def track_factory(app, client, register_user, mock_genius):
    """Импортирует SAMPLE_TRACK и возвращает (client, track)."""
    client.post("/tracks/import/3781")
    with app.app_context():
        from app.models import Track

        track = db.session.scalar(db.select(Track).where(Track.genius_id == "3781"))
    return client, track