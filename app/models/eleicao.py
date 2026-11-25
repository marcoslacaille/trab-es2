"""Tabela `eleicoes`: um pleito em uma data e turno, raiz do agregado de candidaturas."""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Identity,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Eleicao(Base):
    """Um pleito em uma data e turno: a raiz do agregado que contém as candidaturas.

    O status acompanha o ciclo AGENDADA → ABERTA → ENCERRADA (RN-13). Os carimbos de tempo
    são preenchidos pelo serviço com o relógio injetável, nunca pelo banco.
    """

    __tablename__ = "eleicoes"
    __table_args__ = (
        UniqueConstraint("data", "turno"),
        CheckConstraint("turno IN (1, 2)", name="turno_valido"),
        CheckConstraint("horario_abertura < horario_encerramento", name="janela_valida"),
        CheckConstraint("status IN ('AGENDADA','ABERTA','ENCERRADA')", name="status_valido"),
        CheckConstraint(
            "(status = 'AGENDADA'  AND aberta_em IS NULL     AND encerrada_em IS NULL) OR "
            "(status = 'ABERTA'    AND aberta_em IS NOT NULL AND encerrada_em IS NULL) OR "
            "(status = 'ENCERRADA' AND aberta_em IS NOT NULL AND encerrada_em IS NOT NULL)",
            name="status_coerente",
        ),
        # Índice único parcial: o banco garante que só uma eleição fica ABERTA por vez (RN-16).
        Index(
            "uq_eleicoes_uma_aberta",
            "status",
            unique=True,
            postgresql_where=text("status = 'ABERTA'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    descricao: Mapped[str] = mapped_column(String(120))
    data: Mapped[date] = mapped_column(Date)
    turno: Mapped[int] = mapped_column(SmallInteger)
    horario_abertura: Mapped[time] = mapped_column(Time)
    horario_encerramento: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(10), server_default="AGENDADA")
    aberta_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    encerrada_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
