"""retrato das candidaturas: nome de urna e nascimento do candidato gravados na abertura (D-140)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Eleições que já foram abertas antes desta migração ganham o retrato com os dados de agora,
# que é o melhor que existe para elas.
PREENCHER_ELEICOES_JA_ABERTAS = """
UPDATE candidaturas AS candidatura
SET nome_urna = candidato.nome_urna, data_nascimento = candidato.data_nascimento
FROM candidatos AS candidato, eleicoes AS eleicao
WHERE candidato.id = candidatura.candidato_id
  AND eleicao.id = candidatura.eleicao_id
  AND eleicao.status <> 'AGENDADA'
"""


def upgrade() -> None:
    """Acrescenta as colunas do retrato (nulas na eleição AGENDADA) e preenche as já abertas."""
    op.add_column("candidaturas", sa.Column("nome_urna", sa.String(length=30), nullable=True))
    op.add_column("candidaturas", sa.Column("data_nascimento", sa.Date(), nullable=True))
    op.execute(PREENCHER_ELEICOES_JA_ABERTAS)


def downgrade() -> None:
    """Remove as colunas do retrato: a apuração volta a usar os dados atuais do candidato."""
    op.drop_column("candidaturas", "data_nascimento")
    op.drop_column("candidaturas", "nome_urna")
