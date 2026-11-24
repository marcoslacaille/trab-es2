"""Tabelas `eleicoes` e `candidaturas` (seção 6 do PLANO)."""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
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

from app.compartilhado.banco import Base


class Eleicao(Base):
    """Um pleito em uma data e turno: a raiz do agregado que contém as candidaturas.

    O status acompanha o ciclo AGENDADA → ABERTA → ENCERRADA (RN-13). Os carimbos de tempo
    são preenchidos pelo serviço com o relógio injetável, nunca pelo banco (seção 6).
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
