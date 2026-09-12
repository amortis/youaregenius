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
    op.execute(
        """
        UPDATE tracks SET owner_id = (
            SELECT ut.user_id FROM user_tracks ut
            WHERE ut.track_id = tracks.id
            ORDER BY ut.created_at ASC
            LIMIT 1
        )
        """
    )
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.alter_column('owner_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f('ix_tracks_genius_id'))
        batch_op.create_index(batch_op.f('ix_tracks_genius_id'), ['genius_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracks_owner_id'), ['owner_id'], unique=False)
        batch_op.create_unique_constraint('uq_owner_genius', ['owner_id', 'genius_id'])

    op.drop_table('user_tracks')


def downgrade():
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
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.drop_constraint('uq_owner_genius', type_='unique')
        batch_op.drop_index(batch_op.f('ix_tracks_owner_id'))
        batch_op.drop_index(batch_op.f('ix_tracks_genius_id'))
        batch_op.create_index(batch_op.f('ix_tracks_genius_id'), ['genius_id'], unique=True)
        batch_op.alter_column('owner_id', existing_type=sa.Integer(), nullable=True)
    op.drop_column('tracks', 'owner_id')