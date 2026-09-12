import pytest

from app.extensions import db
from app.models import Track, User
from app.services import translation as translation_svc
from conftest import SAMPLE_TRACK


def test_register_and_login_flow(client):
    r = client.post(
        "/auth/register",
        data={"username": "newbie", "password": "secret1", "confirm": "secret1"},
    )
    assert r.status_code == 302 and r.location.endswith("/tracks/my")

    client.post("/auth/logout")
    r = client.post("/auth/login", data={"username": "newbie", "password": "secret1"})
    assert r.status_code == 302


def test_register_rejects_duplicate_username(client):
    client.post(
        "/auth/register",
        data={"username": "dup", "password": "secret1", "confirm": "secret1"},
    )
    r = client.post(
        "/auth/register",
        data={"username": "dup", "password": "other12", "confirm": "other12"},
    )
    assert r.status_code == 400
    assert "уже занято" in r.get_data(as_text=True)


def test_login_wrong_password(client, register_user):
    r = client.post("/auth/login", data={"username": "testuser", "password": "wrongpass"})
    assert r.status_code == 400


@pytest.mark.usefixtures("track_factory")
def test_track_import_and_no_duplicate(app, client):
    with app.app_context():
        assert db.session.query(Track).count() == 1


@pytest.mark.usefixtures("track_factory")
def test_second_user_import_has_own_copy(app):
    second = app.test_client()
    second.post(
        "/auth/register",
        data={"username": "second", "password": "secret1", "confirm": "secret1"},
    )
    second.post("/tracks/import/3781")

    with app.app_context():
        assert db.session.query(Track).count() == 2
        assert User.query.count() == 2


@pytest.mark.usefixtures("track_factory")
def test_annotation_create_and_highlight(client):
    r = client.post(
        "/tracks/1/annotations",
        data={"start": 10, "end": 32, "content": "вопрос о реальности", "translation_id": ""},
    )
    assert r.status_code == 200
    assert "вопрос о реальности" in r.get_data(as_text=True)

    detail = client.get("/tracks/1")
    assert "<mark>Is this the real life?</mark>" in detail.get_data(as_text=True)


def test_annotation_cannot_delete_others(app, client, register_user, track_factory):
    client, _ = track_factory
    with app.app_context():
        from app.models import Annotation, User

        owner = User(username="owner")
        owner.set_password("s3cret99")
        db.session.add(owner)
        db.session.commit()

        annotation = Annotation(
            user_id=owner.id, track_id=1, start_offset=0, end_offset=3,
            content="чужое", excerpt="Is this",
        )
        db.session.add(annotation)
        db.session.commit()
        aid = annotation.id

    # testuser пытается удалить чужую аннотацию
    assert client.post(f"/annotations/{aid}/delete").status_code == 403
    assert client.post(f"/annotations/{aid}/update", data={"content": "хакинг"}).status_code == 403


def test_translation_generate_replaces_existing(app, client, track_factory):
    client, _ = track_factory

    class FakeProvider(translation_svc.TranslationProvider):
        def __init__(self, prefix):
            self.prefix = prefix

        def translate_lines(self, lines, target_lang="RU"):
            return [f"{self.prefix}{line}" for line in lines]

    translation_svc.get_provider = lambda key: FakeProvider("A-")
    client.post("/tracks/1/translate/generate", follow_redirects=True)

    translation_svc.get_provider = lambda key: FakeProvider("B-")
    client.post("/tracks/1/translate/generate", follow_redirects=True)

    with app.app_context():
        from app.models import Translation

        tr = db.session.scalar(db.select(Translation))
        assert tr is not None
        assert tr.structure[0]["lines"] == ["B-Is this the real life?", "B-Is this just fantasy?"]
        assert tr.source == "auto"


def test_translation_generate_without_key_blocks(client, track_factory, monkeypatch):
    monkeypatch.setattr(translation_svc, "get_provider", lambda api_key: None)
    client, _ = track_factory
    r = client.post("/tracks/1/translate/generate", follow_redirects=True)
    assert "DEEPL_API_KEY" in r.get_data(as_text=True)


def test_translation_generate_and_manual_save(app, client, track_factory):
    client, _ = track_factory

    class FakeProvider(translation_svc.TranslationProvider):
        def translate_lines(self, lines, target_lang="RU"):
            return [f"<{line}>" for line in lines]

    translation_svc.get_provider = lambda key: FakeProvider()

    r = client.post("/tracks/1/translate/generate", follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from app.models import Translation

        tr = db.session.scalar(db.select(Translation))
        assert tr is not None
        assert tr.structure[0]["lines"] == ["<Is this the real life?>", "<Is this just fantasy?>"]

    r = client.post(
        "/tracks/1/translate/save",
        data={
            "block_index": ["0", "1"],
            "heading_0": "[Куплет 1]",
            "line_0": "Это настоящая жизнь?",
            "line_1": "Это просто фантазия?",
            "line_2": "Попал в оползень",
            "line_3": "Нет побега от реальности",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "[Куплет 1]" in r.get_data(as_text=True)

    with app.app_context():
        tr = db.session.scalar(db.select(Translation))
        assert tr.source == "manual"
        assert tr.content.startswith("[Куплет 1]\nЭто настоящая жизнь?")


def test_manual_translation_without_key(app, client, track_factory):
    client, _ = track_factory
    r = client.post("/tracks/1/translate/create-manual", follow_redirects=True)
    assert r.status_code == 200
    assert "Сохранить перевод" in r.get_data(as_text=True)

    with app.app_context():
        from app.models import Translation

        tr = db.session.scalar(db.select(Translation))
        assert tr is not None and tr.source == "manual"
        assert tr.structure == [
            {"heading": "[Verse 1]", "lines": ["", ""]},
            {"heading": None, "lines": ["", ""]},
        ]


def test_manual_translation_save_flow(app, client, track_factory):
    client, _ = track_factory
    client.post("/tracks/1/translate/create-manual")
    r = client.post(
        "/tracks/1/translate/save",
        data={
            "block_index": ["0", "1"],
            "heading_0": "[Куплет 1]",
            "line_0": ["Это настоящая жизнь?", "Это просто фантазия?"],
            "line_1": ["Попал в оползень", "Нет побега от реальности"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        from app.models import Translation

        tr = db.session.scalar(db.select(Translation))
        assert tr.source == "manual"
        assert tr.content == "[Куплет 1]\nЭто настоящая жизнь?\nЭто просто фантазия?\n\nПопал в оползень\nНет побега от реальности"


def test_refresh_lyrics_replaces_track(app, client, track_factory, monkeypatch):
    client, _ = track_factory
    from app.services import genius
    from app.services.structures import structure_to_text

    def fresh_scrape(genius_id, user_agent=None):
        data = {**SAMPLE_TRACK, "structure": [{"heading": "[Chorus]", "lines": ["So many losing hope"]}]}
        data["lyrics"] = structure_to_text(data["structure"])
        return data

    monkeypatch.setattr(genius, "scrape_track", fresh_scrape)

    page = client.post("/tracks/1/refresh", follow_redirects=True).get_data(as_text=True)
    assert "Обновить текст с Genius" in page
    with app.app_context():
        t = db.session.get(Track, 1)
        assert t.lyrics == "[Chorus]\nSo many losing hope"
        assert t.structure == [{"heading": "[Chorus]", "lines": ["So many losing hope"]}]
    client, _ = track_factory
    page = client.get("/tracks/1/edit-original").get_data(as_text=True)
    assert "Редактирование текста" in page

    # пустая вторая строка блока 0 и пустые обе строки блока 1 уходят
    client.post(
        "/tracks/1/edit-original",
        data={
            "heading_0": "[Куплет 1]",
            "line_0": ["Is this the real life?", ""],
            "line_1": ["", ""],
        },
        follow_redirects=True,
    )
    with app.app_context():
        t = db.session.get(Track, 1)
        assert t.lyrics == "[Куплет 1]\nIs this the real life?"
        assert t.structure == [
            {"heading": "[Куплет 1]", "lines": ["Is this the real life?"]},
        ]


def test_all_tracks_page(client, track_factory):
    client, track = track_factory
    client.post(
        "/tracks/1/annotations",
        data={"start": 10, "end": 32, "content": "разбор вступления", "translation_id": ""},
    )
    page = client.get("/tracks/all").get_data(as_text=True)
    assert "Все треки" in page
    assert "Bohemian Rhapsody" in page
    assert "A Night at the Opera" in page
    assert "разбор вступления" in page
    assert "testuser" in page


def test_track_card_shows_album(client, track_factory):
    client, _ = track_factory
    page = client.get("/tracks/my").get_data(as_text=True)
    assert "A Night at the Opera" in page
    assert "testuser" in page


def test_non_owner_cannot_annotate_or_translate(app, client, track_factory):
    client, _ = track_factory
    with app.app_context():
        from app.models import User

        intruder = User(username="intruder")
        intruder.set_password("s3cret99")
        db.session.add(intruder)
        db.session.commit()

    client.post("/auth/login", data={"username": "intruder", "password": "s3cret99"})

    r = client.post(
        "/tracks/1/annotations",
        data={"start": 0, "end": 18, "content": "лезу не в свой трек", "translation_id": ""},
    )
    assert r.status_code == 403
    assert client.post("/tracks/1/refresh").status_code == 403
    assert client.get("/tracks/1/editor").status_code == 403
    assert client.get("/tracks/1/edit-original").status_code == 403
    assert client.post("/tracks/1/translate/create-manual").status_code == 403

    pages = client.get("/tracks/1").get_data(as_text=True)
    assert "Редактор аннотаций" not in pages
    assert "Редактировать текст" not in pages
    assert "/tracks/1/translate" not in pages


def test_annotations_list_shows_author(client, track_factory):
    client, _ = track_factory
    client.post(
        "/tracks/1/annotations",
        data={"start": 10, "end": 32, "content": "разбор", "translation_id": ""},
    )
    page = client.get("/tracks/1").get_data(as_text=True)
    assert "testuser" in page
    assert "разбор" in page
    assert 'data-bs-toggle="tooltip"' in page


def test_track_detail_shows_two_languages(app, client, track_factory):
    client, _ = track_factory

    class FakeProvider(translation_svc.TranslationProvider):
        def translate_lines(self, lines, target_lang="RU"):
            return [f"R:{line}" for line in lines]

    translation_svc.get_provider = lambda key: FakeProvider()
    client.post("/tracks/1/translate/generate")
    client.post(
        "/tracks/1/translate/save",
        data={
            "block_index": ["0", "1"],
            "heading_0": "[Куплет 1]",
            "line_0": "Это настоящая жизнь?",
            "line_1": "Это просто фантазия?",
            "line_2": "Попал в оползень",
            "line_3": "Нет побега от реальности",
        },
    )

    page = client.get("/tracks/1").get_data(as_text=True)
    assert "Два языка" in page
    assert "Это настоящая жизнь?" in page
    assert "Is this the real life?" in page