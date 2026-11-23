import os

from sqlalchemy.engine import make_url

URL_TESTE = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste"
)


def conferir_banco_de_teste(url: str) -> None:
    """D-151: a suíte roda `alembic downgrade base` e `TRUNCATE` no banco que recebe.

    Para não apagar o banco da demonstração por engano, só aceita um banco cujo nome termine em
    `_teste` (o local, na porta 5433, e o do CI terminam). Para antes de qualquer conexão.
    """
    nome = make_url(url).database or ""
    if not nome.endswith("_teste"):
        raise RuntimeError(
            f"TEST_DATABASE_URL aponta para o banco '{nome}', que não é de teste: a suíte roda "
            "`alembic downgrade base` e `TRUNCATE` nele. "
            "Use um banco cujo nome termine em `_teste`."
        )


conferir_banco_de_teste(URL_TESTE)
# Nos testes, a própria aplicação aponta para o banco de teste (nunca para o da demo)
os.environ["DATABASE_URL"] = URL_TESTE
os.environ["BCRYPT_CUSTO"] = "4"  # bcrypt rápido nos testes
os.environ.setdefault("JWT_SEGREDO", "segredo-de-teste-com-pelo-menos-32-caracteres")
