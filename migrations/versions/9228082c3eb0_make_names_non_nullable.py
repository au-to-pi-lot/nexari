"""Make names non-nullable

Revision ID: 9228082c3eb0
Revises: f9f9e93e0ead
Create Date: 2024-09-30 19:54:51.007742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9228082c3eb0'
down_revision: Union[str, None] = 'f9f9e93e0ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('channel', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('guild', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('webhook', 'name',
               existing_type=sa.TEXT(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('webhook', 'name',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('guild', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('channel', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###