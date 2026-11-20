"""eleicoes e candidaturas: cria as tabelas eleicoes (com índice parcial) e candidaturas

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `eleicoes` (com o índice parcial de uma eleição aberta) e `candidaturas`."""
    op.create_table(
        "eleicoes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("descricao", sa.String(length=120), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("turno", sa.SmallInteger(), nullable=False),
        sa.Column("horario_abertura", sa.Time(), nullable=False),
        sa.Column("horario_encerramento", sa.Time(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="AGENDADA", nullable=False),
        sa.Column("aberta_em", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("encerrada_em", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'AGENDADA'  AND aberta_em IS NULL     AND encerrada_em IS NULL) OR "
            "(status = 'ABERTA'    AND aberta_em IS NOT NULL AND encerrada_em IS NULL) OR "
            "(status = 'ENCERRADA' AND aberta_em IS NOT NULL AND encerrada_em IS NOT NULL)",
            name=op.f("ck_eleicoes_status_coerente"),
        ),
        sa.CheckConstraint(
            "status IN ('AGENDADA','ABERTA','ENCERRADA')", name=op.f("ck_eleicoes_status_valido")
        ),
        sa.CheckConstraint(
            "horario_abertura < horario_encerramento", name=op.f("ck_eleicoes_janela_valida")
        ),
        sa.CheckConstraint("turno IN (1, 2)", name=op.f("ck_eleicoes_turno_valido")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eleicoes")),
        sa.UniqueConstraint("data", "turno", name=op.f("uq_eleicoes_data_turno")),
    )
    op.create_index(
        "uq_eleicoes_uma_aberta",
        "eleicoes",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ABERTA'"),
    )
    op.create_table(
        "candidaturas",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("eleicao_id", sa.BigInteger(), nullable=False),
        sa.Column("candidato_id", sa.BigInteger(), nullable=False),
        sa.Column("partido_id", sa.BigInteger(), nullable=False),
        sa.Column("cargo", sa.String(length=20), nullable=False),
        sa.Column("numero", sa.String(length=5), nullable=False),
        sa.Column("criado_em", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(cargo IN ('PRESIDENTE', 'GOVERNADOR') AND numero ~ '^[1-9][0-9]$') OR "
            "(cargo = 'SENADOR'           AND numero ~ '^[1-9][0-9]{2}$') OR "
            "(cargo = 'DEPUTADO_FEDERAL'  AND numero ~ '^[1-9][0-9]{3}$') OR "
            "(cargo = 'DEPUTADO_ESTADUAL' AND numero ~ '^[1-9][0-9]{4}$')",
            name=op.f("ck_candidaturas_numero_por_cargo"),
        ),
        sa.CheckConstraint(
            "cargo IN ('DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','SENADOR','GOVERNADOR','PRESIDENTE')",
            name=op.f("ck_candidaturas_cargo_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["candidato_id"],
            ["candidatos.id"],
            name=op.f("fk_candidaturas_candidato_id_candidatos"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["eleicao_id"],
            ["eleicoes.id"],
            name=op.f("fk_candidaturas_eleicao_id_eleicoes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partido_id"],
            ["partidos.id"],
            name=op.f("fk_candidaturas_partido_id_partidos"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidaturas")),
        sa.UniqueConstraint(
            "eleicao_id", "candidato_id", name=op.f("uq_candidaturas_eleicao_id_candidato_id")
        ),
        sa.UniqueConstraint(
            "eleicao_id", "cargo", "numero", name=op.f("uq_candidaturas_eleicao_id_cargo_numero")
        ),
        sa.UniqueConstraint(
            "id", "eleicao_id", "cargo", name=op.f("uq_candidaturas_id_eleicao_id_cargo")
        ),
    )


def downgrade() -> None:
    """Remove `candidaturas` e `eleicoes`."""
    op.drop_table("candidaturas")
    op.drop_index(
        "uq_eleicoes_uma_aberta",
        table_name="eleicoes",
        postgresql_where=sa.text("status = 'ABERTA'"),
    )
    op.drop_table("eleicoes")
