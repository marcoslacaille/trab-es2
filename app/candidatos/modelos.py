"""Tabelas `candidatos` e `partidos` (seção 6 do PLANO)."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.compartilhado.banco import Base


class Candidato(Base):
    """A pessoa que disputa cargos. Nome e CPF ficam na credencial (`usuarios`).

    Não é a candidatura: ligar o candidato a uma eleição, cargo e número é trabalho do módulo
    `eleicoes`. A chave estrangeira aponta para `usuarios` pelo nome da tabela em texto.
    """

    __tablename__ = "candidatos"
    __table_args__ = (UniqueConstraint("usuario_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    nome_urna: Mapped[str] = mapped_column(String(30))
    # Usada no desempate por idade da apuração (RN-78).
    data_nascimento: Mapped[date] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Partido(Base):
    """Agremiação com sigla, nome e número de 2 dígitos, os três únicos (RN-32)."""

    __tablename__ = "partidos"
    __table_args__ = (
        UniqueConstraint("sigla"),
        UniqueConstraint("nome"),
        UniqueConstraint("numero"),
        CheckConstraint("sigla ~ '^[A-Z0-9]{2,10}$'", name="sigla_formato"),
        CheckConstraint("numero BETWEEN 10 AND 99", name="numero_faixa"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sigla: Mapped[str] = mapped_column(String(10))
    nome: Mapped[str] = mapped_column(String(100))
    numero: Mapped[int] = mapped_column(SmallInteger)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
