"""per-user tracks: owner_id, drop user_tracks

Revision ID: 6f2c91a4d5b0
Revises: 597184073edc
Create Date: 2026-09-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f2c91a4d5b0'
down_revision = '597184073edc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'owner_id',
                sa.Integer(),
                sa.ForeignKey('users.id', name='fk_tracks_owner_id'),
                nullable=True,
            )
        )
    # Reflect the historical schema rather than importing today's ORM models.
    connection = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=connection)
    tracks = metadata.tables['tracks']
    users = metadata.tables['users']
    links = metadata.tables['user_tracks']
    translations = metadata.tables['translations']
    annotations = metadata.tables['annotations']
    for track in connection.execute(sa.select(tracks)).mappings().all():
        owners = list(connection.scalars(
            sa.select(links.c.user_id).where(links.c.track_id == track['id'])
            .order_by(links.c.created_at, links.c.user_id)
        ))
        # Also preserve users whose translations/notes outlived a collection link.
        for table in (translations, annotations):
            for user_id in connection.scalars(
                sa.select(table.c.user_id).where(table.c.track_id == track['id'])
                .distinct().order_by(table.c.user_id)
            ):
                if user_id not in owners:
                    owners.append(user_id)
        if not owners:
            fallback = connection.scalar(sa.select(users.c.id).order_by(users.c.id).limit(1))
            if fallback is None:
                raise RuntimeError("Cannot assign an orphan track: create a user before upgrading.")
            owners = [fallback]
        connection.execute(tracks.update().where(tracks.c.id == track['id']).values(owner_id=owners[0]))
        # Remove global uniqueness before making personal copies below.
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.alter_column('owner_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f('ix_tracks_genius_id'))
        batch_op.create_index(batch_op.f('ix_tracks_genius_id'), ['genius_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_owner_id'), ['owner_id'], unique=False)
        batch_op.create_unique_constraint('uq_owner_genius', ['owner_id', 'genius_id'])

    for track in connection.execute(sa.select(tracks)).mappings().all():
        owner_ids = set(connection.scalars(sa.select(links.c.user_id).where(links.c.track_id == track['id'])))
        for table in (translations, annotations):
            owner_ids.update(connection.scalars(sa.select(table.c.user_id).where(table.c.track_id == track['id'])))
        for owner_id in sorted(owner_ids - {track['owner_id']}):
            values = {key: value for key, value in track.items() if key != 'id'}
            values['owner_id'] = owner_id
            new_id = connection.execute(tracks.insert().values(**values)).inserted_primary_key[0]
            connection.execute(translations.update().where(
                translations.c.track_id == track['id'], translations.c.user_id == owner_id
            ).values(track_id=new_id))
            connection.execute(annotations.update().where(
                annotations.c.track_id == track['id'], annotations.c.user_id == owner_id
            ).values(track_id=new_id))

    op.drop_table('user_tracks')


def downgrade():
    connection = op.get_bind()
    duplicates = connection.execute(sa.text(
        "SELECT genius_id FROM tracks GROUP BY genius_id HAVING COUNT(*) > 1"
    )).first()
    if duplicates:
        raise RuntimeError("Cannot downgrade personal copies to globally unique tracks; merge duplicate Genius IDs first.")
    op.create_table(
        'user_tracks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'track_id', name='uq_user_track'),
    )
    op.execute("INSERT INTO user_tracks (user_id, track_id, created_at) SELECT owner_id, id, created_at FROM tracks")
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.drop_constraint('uq_owner_genius', type_='unique')
        batch_op.drop_index(batch_op.f('ix_tracks_owner_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_genius_id'))
        batch_op.create_index(batch_op.f('ix_tracks_genius_id'), ['genius_id'], unique=True)
        batch_op.drop_constraint('fk_tracks_owner_id', type_='foreignkey')
        batch_op.drop_column('owner_id')