"""Tabela `usuarios`: a credencial de quem faz login."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Identity, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR

from app.core.database import Base


class Usuario(Base):
    """Credencial de acesso. Todo eleitor, candidato e chefe da seção tem uma (RN-03).

    Os nomes das restrições seguem a convenção do `banco.py` (ex.: `uq_usuarios_cpf`),
    para a aplicação traduzir uma violação em erro amigável.
    """

    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("cpf"),
        CheckConstraint("cpf ~ '^[0-9]{11}$'", name="cpf_digitos"),
        CheckConstraint("char_length(trim(nome)) >= 3", name="nome_minimo"),
        CheckConstraint("perfil IN ('CHEFE_SECAO','ELEITOR','CANDIDATO')", name="perfil_valido"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cpf: Mapped[str] = mapped_column(CHAR(11))
    nome: Mapped[str] = mapped_column(String(120))
    # Só o hash bcrypt é gravado; a senha em si nunca (RN-05).
    senha_hash: Mapped[str] = mapped_column(String(60))
    perfil: Mapped[str] = mapped_column(String(20))
    # Preenchidos pelo serviço com o relógio injetável, não por DEFAULT do banco (seção 6).
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
