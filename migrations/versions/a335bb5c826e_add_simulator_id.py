"""Add simulator_id

Revision ID: a335bb5c826e
Revises: 091536e0bd7a
Create Date: 2024-09-28 06:04:32.110919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a335bb5c826e'
down_revision: Union[str, None] = '091536e0bd7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('guild', sa.Column('simulator_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 'guild', 'llm', ['simulator_id'], ['id'])
    op.create_foreign_key(None, 'guild', 'channel', ['simulator_channel_id'], ['id'])
    op.add_column('llm', sa.Column('instruct_tuned', sa.Boolean(), nullable=False, server_default=sa.sql.true()))
    op.add_column('llm', sa.Column('message_formatter', sa.String(), nullable=False, server_default="irc"))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('llm', 'message_formatter')
    op.drop_column('llm', 'instruct_tuned')
    op.drop_constraint(None, 'guild', type_='foreignkey')
    op.drop_constraint(None, 'guild', type_='foreignkey')
    op.drop_column('guild', 'simulator_id')
    # ### end Alembic commands ###