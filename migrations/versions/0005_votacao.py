"""votacao: cria registros_votacao e votos (sem ligação entre si) e o trigger de imutabilidade

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CARGOS_VALIDOS = (
    "cargo IN ('DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','SENADOR','GOVERNADOR','PRESIDENTE')"
)


FUNCAO_IMPEDIR_ALTERACAO = """
CREATE FUNCTION impedir_alteracao_de_voto() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Votos e registros de votação confirmados são imutáveis';
END;
$$ LANGUAGE plpgsql
"""

TRIGGER_VOTOS = """
CREATE TRIGGER trg_votos_imutaveis
    BEFORE UPDATE OR DELETE ON votos
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_de_voto()
"""

TRIGGER_REGISTROS = """
CREATE TRIGGER trg_registros_votacao_imutaveis
    BEFORE UPDATE OR DELETE ON registros_votacao
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_de_voto()
"""


def upgrade() -> None:
    """Cria as tabelas (quem votou e o quê, sem coluna que as una) e o trigger de imutabilidade."""
    op.create_table(
        "registros_votacao",
        sa.Column("eleitor_id", sa.BigInteger(), nullable=False),
        sa.Column("eleicao_id", sa.BigInteger(), nullable=False),
        sa.Column("cargo", sa.String(length=20), nullable=False),
        sa.CheckConstraint(CARGOS_VALIDOS, name=op.f("ck_registros_votacao_cargo_valido")),
        sa.ForeignKeyConstraint(
            ["eleicao_id"],
            ["eleicoes.id"],
            name=op.f("fk_registros_votacao_eleicao_id_eleicoes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["eleitor_id"],
            ["eleitores.id"],
            name=op.f("fk_registros_votacao_eleitor_id_eleitores"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "eleitor_id", "eleicao_id", "cargo", name=op.f("pk_registros_votacao")
        ),
    )
    op.create_index(
        op.f("ix_registros_votacao_eleicao_id"), "registros_votacao", ["eleicao_id"], unique=False
    )
    op.create_table(
        "votos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("eleicao_id", sa.BigInteger(), nullable=False),
        sa.Column("cargo", sa.String(length=20), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("candidatura_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "(tipo = 'NOMINAL') = (candidatura_id IS NOT NULL)",
            name=op.f("ck_votos_nominal_tem_candidatura"),
        ),
        sa.CheckConstraint(CARGOS_VALIDOS, name=op.f("ck_votos_cargo_valido")),
        sa.CheckConstraint(
            "tipo IN ('NOMINAL','BRANCO','NULO')", name=op.f("ck_votos_tipo_valido")
        ),
        sa.ForeignKeyConstraint(
            ["candidatura_id", "eleicao_id", "cargo"],
            ["candidaturas.id", "candidaturas.eleicao_id", "candidaturas.cargo"],
            name="fk_votos_candidatura_id_candidaturas",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["eleicao_id"],
            ["eleicoes.id"],
            name=op.f("fk_votos_eleicao_id_eleicoes"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_votos")),
    )
    op.create_index(
        "ix_votos_apuracao", "votos", ["eleicao_id", "cargo", "candidatura_id"], unique=False
    )
    # O autogenerate não cria trigger: voto e registro confirmados nunca mudam (RN-59).
    op.execute(FUNCAO_IMPEDIR_ALTERACAO)
    op.execute(TRIGGER_VOTOS)
    op.execute(TRIGGER_REGISTROS)


def downgrade() -> None:
    """Remove os triggers e a função, depois `votos` e `registros_votacao`."""
    op.execute("DROP TRIGGER trg_registros_votacao_imutaveis ON registros_votacao")
    op.execute("DROP TRIGGER trg_votos_imutaveis ON votos")
    op.execute("DROP FUNCTION impedir_alteracao_de_voto()")
    op.drop_index("ix_votos_apuracao", table_name="votos")
    op.drop_table("votos")
    op.drop_index(op.f("ix_registros_votacao_eleicao_id"), table_name="registros_votacao")
    op.drop_table("registros_votacao")
