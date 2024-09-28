"""Alter check constraint on message

Revision ID: 091536e0bd7a
Revises: 140d9f5227dc
Create Date: 2024-09-27 19:34:01.937623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '091536e0bd7a'
down_revision: Union[str, None] = '140d9f5227dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old constraint
    op.drop_constraint('user_xor_webhook', 'message', type_='check')

    # Add the new constraint
    op.create_check_constraint(
        'user_xor_webhook_or_both_null',
        'message',
        '(user_id IS NULL AND webhook_id IS NULL) OR (user_id IS NOT NULL) != (webhook_id IS NOT NULL)'
    )


def downgrade() -> None:
    # Drop the new constraint
    op.drop_constraint('user_xor_webhook_or_both_null', 'message', type_='check')

    # Add back the old constraint
    op.create_check_constraint(
        'user_xor_webhook',
        'message',
        '(user_id IS NOT NULL) != (webhook_id IS NOT NULL)'
    )
