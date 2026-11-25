"""Banco de dados: `Base` do ORM, `engine`, `SessionLocal` e a sessão de cada requisição."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import obter_configuracao

# Toda restrição tem nome previsível, para a aplicação traduzir uma violação do banco
# em um código de erro amigável.
CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base de todos os modelos ORM, com a convenção de nomes das restrições."""

    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)


# hide_parameters: a mensagem de erro do banco não leva os valores do SQL (hash da senha, CPF,
# nome), que senão iriam para o log do erro 500.
engine = create_engine(obter_configuracao().database_url, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    """Abre uma sessão por requisição, entrega a quem pediu e a fecha no final.

    Fechar a sessão sem commit desfaz tudo o que não foi confirmado.
    """
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()
