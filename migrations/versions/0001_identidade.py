"""identidade: cria a tabela usuarios

Revision ID: 0001
Revises:
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `usuarios` com as restrições nomeadas pela convenção de app/core/database.py."""
    op.create_table(
        "usuarios",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("cpf", sa.CHAR(length=11), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("senha_hash", sa.String(length=60), nullable=False),
        sa.Column("perfil", sa.String(length=20), nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("atualizado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("cpf ~ '^[0-9]{11}$'", name=op.f("ck_usuarios_cpf_digitos")),
        sa.CheckConstraint(
            "perfil IN ('CHEFE_SECAO','ELEITOR','CANDIDATO')",
            name=op.f("ck_usuarios_perfil_valido"),
        ),
        sa.CheckConstraint("char_length(trim(nome)) >= 3", name=op.f("ck_usuarios_nome_minimo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("cpf", name=op.f("uq_usuarios_cpf")),
    )


def downgrade() -> None:
    """Remove `usuarios`."""
    op.drop_table("usuarios")
