"""Tabela `candidaturas`: o candidato em uma eleição, com cargo, partido e número."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Candidatura(Base):
    """Associação de um candidato a uma eleição, com cargo, partido e número.

    Entidade interna do agregado `Eleicao`: só muda pela eleição. As chaves estrangeiras
    apontam para as tabelas de outros módulos pelo nome em texto. A restrição
    `uq_candidaturas_id_eleicao_id_cargo` é o alvo da chave estrangeira composta de `votos`.
    """

    __tablename__ = "candidaturas"
    __table_args__ = (
        UniqueConstraint("eleicao_id", "cargo", "numero"),
        UniqueConstraint("eleicao_id", "candidato_id"),
        UniqueConstraint("id", "eleicao_id", "cargo"),
        CheckConstraint(
            "cargo IN ('DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','SENADOR','GOVERNADOR','PRESIDENTE')",
            name="cargo_valido",
        ),
        CheckConstraint(
            "(cargo IN ('PRESIDENTE', 'GOVERNADOR') AND numero ~ '^[1-9][0-9]$') OR "
            "(cargo = 'SENADOR'           AND numero ~ '^[1-9][0-9]{2}$') OR "
            "(cargo = 'DEPUTADO_FEDERAL'  AND numero ~ '^[1-9][0-9]{3}$') OR "
            "(cargo = 'DEPUTADO_ESTADUAL' AND numero ~ '^[1-9][0-9]{4}$')",
            name="numero_por_cargo",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    eleicao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eleicoes.id", ondelete="RESTRICT")
    )
    candidato_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidatos.id", ondelete="RESTRICT")
    )
    partido_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("partidos.id", ondelete="RESTRICT")
    )
    cargo: Mapped[str] = mapped_column(String(20))
    numero: Mapped[str] = mapped_column(String(5))
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    # Retrato do candidato gravado na abertura (D-140): editar o candidato depois não muda a
    # eleição ABERTA ou ENCERRADA. Nulos enquanto a eleição está AGENDADA.
    nome_urna: Mapped[str | None] = mapped_column(String(30))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
