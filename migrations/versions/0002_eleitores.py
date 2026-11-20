"""eleitores: cria a tabela eleitores

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `eleitores` com as restrições nomeadas pela convenção do banco.py."""
    op.create_table(
        "eleitores",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("titulo_eleitor", sa.CHAR(length=12), nullable=False),
        sa.Column("data_nascimento", sa.Date(), nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "titulo_eleitor ~ '^[0-9]{12}$'", name=op.f("ck_eleitores_titulo_digitos")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_eleitores_usuario_id_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eleitores")),
        sa.UniqueConstraint("titulo_eleitor", name=op.f("uq_eleitores_titulo_eleitor")),
        sa.UniqueConstraint("usuario_id", name=op.f("uq_eleitores_usuario_id")),
    )


def downgrade() -> None:
    """Remove `eleitores`."""
    op.drop_table("eleitores")
