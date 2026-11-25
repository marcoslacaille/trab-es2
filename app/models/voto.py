"""Tabela `votos`: o que foi votado, sem ligação com `registros_votacao` (RN-60)."""

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import CARGOS_VALIDOS


class Voto(Base):
    """O que foi votado. Não diz quem votou: sem `eleitor_id`, sem horário, sem id sequencial.

    O `id` é um UUID aleatório gerado pela aplicação, que não revela a ordem de gravação.
    A chave estrangeira composta garante que um voto para Senador nunca aponta para uma
    candidatura a Presidente, nem de outra eleição (RN-60).
    """

    __tablename__ = "votos"
    __table_args__ = (
        CheckConstraint(CARGOS_VALIDOS, name="cargo_valido"),
        CheckConstraint("tipo IN ('NOMINAL','BRANCO','NULO')", name="tipo_valido"),
        CheckConstraint(
            "(tipo = 'NOMINAL') = (candidatura_id IS NOT NULL)", name="nominal_tem_candidatura"
        ),
        # Com `candidatura_id` nulo (BRANCO ou NULO) a chave composta não é verificada.
        ForeignKeyConstraint(
            ["candidatura_id", "eleicao_id", "cargo"],
            ["candidaturas.id", "candidaturas.eleicao_id", "candidaturas.cargo"],
            ondelete="RESTRICT",
            name="fk_votos_candidatura_id_candidaturas",
        ),
        Index("ix_votos_apuracao", "eleicao_id", "cargo", "candidatura_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eleicao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eleicoes.id", ondelete="RESTRICT")
    )
    cargo: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(10))
    candidatura_id: Mapped[int | None] = mapped_column(BigInteger)
