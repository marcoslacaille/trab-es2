"""A suíte só aceita rodar num banco de teste."""

import pytest

from tests.conftest import conferir_banco_de_teste


def test_aceita_banco_cujo_nome_termina_em_teste():
    """O banco local (porta 5433) e o do CI terminam em `_teste` e passam."""
    conferir_banco_de_teste("postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://eleicao:eleicao@localhost:5432/eleicao",
        "postgresql+psycopg://eleicao:eleicao@localhost:5432/postgres",
        "postgresql+psycopg://eleicao:eleicao@localhost:5433/teste_eleicao",
        "postgresql+psycopg://eleicao:eleicao@localhost:5433",
    ],
)
def test_recusa_banco_que_nao_e_de_teste(url):
    """O banco da demonstração, o padrão do PostgreSQL ou um sem nome param a suíte."""
    with pytest.raises(RuntimeError, match="não é de teste"):
        conferir_banco_de_teste(url)
