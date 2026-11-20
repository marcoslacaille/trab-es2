"""candidatos e partidos: cria as tabelas candidatos e partidos

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `partidos` e `candidatos` com as restrições nomeadas pela convenção do banco.py."""
    op.create_table(
        "partidos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sigla", sa.String(length=10), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("numero", sa.SmallInteger(), nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("sigla ~ '^[A-Z0-9]{2,10}$'", name=op.f("ck_partidos_sigla_formato")),
        sa.CheckConstraint("numero BETWEEN 10 AND 99", name=op.f("ck_partidos_numero_faixa")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partidos")),
        sa.UniqueConstraint("nome", name=op.f("uq_partidos_nome")),
        sa.UniqueConstraint("numero", name=op.f("uq_partidos_numero")),
        sa.UniqueConstraint("sigla", name=op.f("uq_partidos_sigla")),
    )
    op.create_table(
        "candidatos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("nome_urna", sa.String(length=30), nullable=False),
        sa.Column("data_nascimento", sa.Date(), nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_candidatos_usuario_id_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidatos")),
        sa.UniqueConstraint("usuario_id", name=op.f("uq_candidatos_usuario_id")),
    )


def downgrade() -> None:
    """Remove `candidatos` e `partidos`."""
    op.drop_table("candidatos")
    op.drop_table("partidos")
