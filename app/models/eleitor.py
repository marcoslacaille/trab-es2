"""Tabela `eleitores`: os dados de quem pode votar."""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Identity, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR

from app.core.database import Base


class Eleitor(Base):
    """Eleitor cadastrado pelo Chefe da Seção. Nome e CPF ficam na credencial (`usuarios`).

    A chave estrangeira aponta para `usuarios` pelo nome da tabela em texto, sem importar o
    model do usuário. Os nomes das restrições seguem a convenção de `core/database.py`
    (ex.: `uq_eleitores_titulo_eleitor`), para a aplicação traduzi-las em erros amigáveis.
    """

    __tablename__ = "eleitores"
    __table_args__ = (
        UniqueConstraint("usuario_id"),
        UniqueConstraint("titulo_eleitor"),
        CheckConstraint("titulo_eleitor ~ '^[0-9]{12}$'", name="titulo_digitos"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    titulo_eleitor: Mapped[str] = mapped_column(CHAR(12))
    data_nascimento: Mapped[date] = mapped_column(Date)
    # Preenchido pelo serviço com o relógio injetável. A apuração usa este carimbo
    # para saber se o eleitor já estava cadastrado quando a eleição foi aberta (RN-53).
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
