"""A suíte só aceita rodar num banco de teste."""

import pytest

from tests.conftest import URL_PADRAO, conferir_banco_de_teste, url_do_banco_de_teste


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


def test_url_do_ambiente_vale_mais_que_a_do_env_e_a_do_padrao(tmp_path):
    """O CI informa o banco pelo ambiente; sem ele vale o `.env`; sem os dois, o padrão."""
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "POSTGRES_PASSWORD=outra\n"
        "TEST_DATABASE_URL=postgresql+psycopg://eleicao:outra@localhost:5433/eleicao_teste\n",
        encoding="utf-8",
    )
    do_ambiente = "postgresql+psycopg://eleicao:ci@localhost:5433/eleicao_teste"

    assert url_do_banco_de_teste({"TEST_DATABASE_URL": do_ambiente}, arquivo) == do_ambiente
    assert url_do_banco_de_teste({}, arquivo) == (
        "postgresql+psycopg://eleicao:outra@localhost:5433/eleicao_teste"
    )
    assert url_do_banco_de_teste({}, tmp_path / "sem.env") == URL_PADRAO
