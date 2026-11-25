"""Tabela `registros_votacao`: quem já votou em cada cargo, sem ligação com `votos` (RN-60)."""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import CARGOS_VALIDOS


class RegistroVotacao(Base):
    """Marca que o eleitor já votou em um cargo de uma eleição. Não diz em quem (RN-54, RN-60).

    A chave primária composta é o que impede o voto duplo, mesmo com duas requisições
    simultâneas. Sem coluna de horário e sem coluna de candidatura, de propósito.
    """

    __tablename__ = "registros_votacao"
    __table_args__ = (CheckConstraint(CARGOS_VALIDOS, name="cargo_valido"),)

    eleitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eleitores.id", ondelete="RESTRICT"), primary_key=True
    )
    eleicao_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("eleicoes.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    cargo: Mapped[str] = mapped_column(String(20), primary_key=True)
