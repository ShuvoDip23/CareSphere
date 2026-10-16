"""merge chat and donor migrations

Revision ID: 9e4c6fe839de
Revises: 5c8855394067, 7bcf62b54f6a
Create Date: 2026-10-12 16:43:00.890229

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e4c6fe839de'
down_revision = ('5c8855394067', '7bcf62b54f6a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
