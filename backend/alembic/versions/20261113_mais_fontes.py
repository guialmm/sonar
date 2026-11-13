"""mais fontes: smartrecruiters, himalayas, remotive, adzuna

Revision ID: b3f1c2d4e5a6
Revises: a771fc56fe30
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3f1c2d4e5a6"
down_revision: Union[str, Sequence[str], None] = "a771fc56fe30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOVAS = ("smartrecruiters", "himalayas", "remotive", "adzuna")


def upgrade() -> None:
    for valor in NOVAS:
        op.execute(f"ALTER TYPE fonte ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    # Postgres can't drop an enum value; the extra labels are harmless.
    pass
