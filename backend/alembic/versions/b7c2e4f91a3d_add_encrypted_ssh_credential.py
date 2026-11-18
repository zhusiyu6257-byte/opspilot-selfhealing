"""add encrypted ssh credential to assets

Revision ID: b7c2e4f91a3d
Revises: 9acdf4797c0e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7c2e4f91a3d'
down_revision: Union[str, Sequence[str], None] = '9acdf4797c0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 可空：旧主机继续沿用免密密钥登录，不需要批量补录密码
    op.add_column(
        'assets',
        sa.Column('ssh_password_encrypted', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('assets', 'ssh_password_encrypted')
