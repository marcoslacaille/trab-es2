import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# O banco de teste do `docker compose` com os valores do `.env.example`.
URL_PADRAO = "postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste"
ARQUIVO_ENV = Path(__file__).resolve().parents[1] / ".env"


def url_do_banco_de_teste(ambiente: Mapping[str, str], arquivo_env: Path) -> str:
    """O `TEST_DATABASE_URL` do ambiente; senão o do `.env` da raiz; senão o padrão do compose.

    O ambiente vale mais porque é por ele que o CI informa o banco. O `.env` vale para quem
    trocou a senha ou a porta, como o README sugere fora da demonstração: o `docker compose`
    sobe o banco de teste com os valores do `.env`, e a suíte precisa usar os mesmos.
    """
    if ambiente.get("TEST_DATABASE_URL"):
        return ambiente["TEST_DATABASE_URL"]
    if arquivo_env.is_file():
        do_arquivo = dotenv_values(arquivo_env).get("TEST_DATABASE_URL")
        if do_arquivo:
            return do_arquivo
    return URL_PADRAO


URL_TESTE = url_do_banco_de_teste(os.environ, ARQUIVO_ENV)


def conferir_banco_de_teste(url: str) -> None:
    """A suíte roda `alembic downgrade base` e `TRUNCATE` no banco que recebe.

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
