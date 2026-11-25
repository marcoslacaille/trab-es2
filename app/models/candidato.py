"""Tabela `candidatos`: a pessoa que disputa cargos."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
    # Usada no desempate por idade da apuração (RN-77).
    data_nascimento: Mapped[date] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
