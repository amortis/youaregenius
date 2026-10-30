import pytest
import sqlalchemy as sa
from flask_migrate import upgrade, downgrade
from app.extensions import db


def test_migrations_fresh_database_and_roundtrip(app):
    with app.app_context():
        db.drop_all()
        upgrade()
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        with db.engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []
        downgrade(revision="base")
        assert sa.inspect(db.engine).get_table_names() == ["alembic_version"]
        upgrade()


@pytest.mark.parametrize("linked", [True, False])
def test_migration_preserves_personal_data(app, linked):
    with app.app_context():
        db.drop_all()
        upgrade(revision="597184073edc")
        with db.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO users (id, username, password_hash, created_at) VALUES (1, 'one', 'x', CURRENT_TIMESTAMP), (2, 'two', 'x', CURRENT_TIMESTAMP)"))
            connection.execute(sa.text("INSERT INTO tracks (id, genius_id, title, artist, lyrics, structure, created_at) VALUES (1, '42', 'Song', 'Artist', 'Line', '[]', CURRENT_TIMESTAMP)"))
            if linked:
                connection.execute(sa.text("INSERT INTO user_tracks (user_id, track_id, created_at) VALUES (1, 1, CURRENT_TIMESTAMP), (2, 1, CURRENT_TIMESTAMP)"))
            connection.execute(sa.text("INSERT INTO translations (id, user_id, track_id, lang, content, structure, source, created_at, updated_at) VALUES (1, 2, 1, 'ru', 'Text', '[]', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            connection.execute(sa.text("INSERT INTO annotations (user_id, track_id, translation_id, start_offset, end_offset, content, excerpt, created_at, updated_at) VALUES (2, 1, 1, 0, 4, 'Note', 'Line', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        upgrade()
        with db.engine.connect() as connection:
            assert connection.execute(sa.text("SELECT COUNT(*) FROM tracks")).scalar() == (2 if linked else 1)
            assert connection.execute(sa.text("SELECT t.owner_id FROM tracks t JOIN translations tr ON tr.track_id=t.id")).scalar() == 2
            assert connection.execute(sa.text("SELECT t.owner_id FROM tracks t JOIN annotations a ON a.track_id=t.id")).scalar() == 2
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        if linked:
            with pytest.raises(SystemExit) as error:
                downgrade(revision="597184073edc")
            assert error.value.code == 1
            with db.engine.connect() as connection:
                assert connection.execute(sa.text("SELECT COUNT(*) FROM tracks")).scalar() == 2
        else:
            downgrade(revision="597184073edc")
            with db.engine.connect() as connection:
                assert connection.execute(sa.text("SELECT user_id FROM user_tracks")).scalar() == 2
            upgrade()
