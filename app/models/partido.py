"""Tabela `partidos`: as agremiações, com sigla, nome e número de 2 dígitos."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
