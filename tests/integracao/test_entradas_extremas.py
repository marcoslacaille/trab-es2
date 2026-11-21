"""Entradas no limite: nenhuma delas pode virar erro 500 (seção 7, "Erros sem vazamento").

Achados do teste de caixa-preta contra a API real (D-128 a D-130): ID maior que o BIGINT do
PostgreSQL, caractere nulo em campo de texto e valores do SQL no log de erro.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.compartilhado.banco import SessionLocal
from app.compartilhado.config import obter_configuracao
from app.identidade.tokens import ALGORITMO, AUDIENCIA_ACESSO
from tests.auxiliares import nova_eleicao, novo_candidato, novo_eleitor, novo_partido

ID_GIGANTE = 10**20  # maior que 9.223.372.036.854.775.807 (BIGINT)


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


@pytest.mark.parametrize(
    "caminho",
    [
        f"/api/v1/eleicoes/{ID_GIGANTE}",
        f"/api/v1/eleitores/{ID_GIGANTE}",
        f"/api/v1/candidatos/{ID_GIGANTE}",
        f"/api/v1/eleicoes/1/candidaturas/{ID_GIGANTE}",
        f"/api/v1/apuracao/eleicoes/{ID_GIGANTE}/parcial",
        f"/api/v1/apuracao/eleicoes/{ID_GIGANTE}/resultado",
    ],
)
def test_id_de_caminho_maior_que_bigint_responde_422(cliente, cabecalho_chefe, caminho):
    """Seção 10: ID de caminho fora da faixa do BIGINT é pedido errado (422), não erro 500."""
    metodo = "DELETE" if "candidaturas" in caminho else "GET"

    resposta = cliente.request(metodo, caminho, headers=cabecalho_chefe)

    assert resposta.status_code == 422
    assert _codigo(resposta) == "DADOS_INVALIDOS"


def test_id_da_votacao_maior_que_bigint_responde_422(cliente, cabecalho_eleitor):
    """Seção 10: a cédula com ID gigante também é recusada na entrada (422)."""
    resposta = cliente.get(
        f"/api/v1/votacao/eleicoes/{ID_GIGANTE}/cedula", headers=cabecalho_eleitor
    )

    assert resposta.status_code == 422


def test_id_gigante_no_corpo_da_candidatura_responde_422(cliente, cabecalho_chefe):
    """RN-46: candidato_id fora da faixa do BIGINT é recusado no esquema (422), não no banco."""
    eleicao_id = nova_eleicao(cliente, cabecalho_chefe).json()["id"]
    partido_id = novo_partido(cliente, cabecalho_chefe).json()["id"]
    corpo = {"candidato_id": ID_GIGANTE, "partido_id": partido_id, "cargo": "GOVERNADOR"}

    resposta = cliente.post(
        f"/api/v1/eleicoes/{eleicao_id}/candidaturas",
        json={**corpo, "numero": "11"},
        headers=cabecalho_chefe,
    )

    assert resposta.status_code == 422
    assert _codigo(resposta) == "DADOS_INVALIDOS"


def test_token_com_sub_maior_que_bigint_responde_401(cliente):
    """RN-02: token bem assinado, mas com `sub` fora da faixa de IDs, vira TOKEN_INVALIDO."""
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(ID_GIGANTE),
            "aud": AUDIENCIA_ACESSO,
            "iat": agora,
            "exp": agora + timedelta(minutes=5),
        },
        obter_configuracao().jwt_segredo,
        algorithm=ALGORITMO,
    )

    resposta = cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 401
    assert _codigo(resposta) == "TOKEN_INVALIDO"


@pytest.mark.parametrize(
    ("cadastrar", "campo"),
    [
        (novo_eleitor, "nome"),
        (novo_candidato, "nome"),
        (novo_candidato, "nome_urna"),
        (novo_partido, "nome"),
        (nova_eleicao, "descricao"),
    ],
)
def test_caractere_nulo_em_campo_de_texto_responde_422(cliente, cabecalho_chefe, cadastrar, campo):
    """RN-08: texto com o caractere nulo é recusado no esquema (422), não no banco (500)."""
    resposta = cadastrar(cliente, cabecalho_chefe, **{campo: "Ana\x00Maria"})

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["detalhes"]["campos"] == [
        {"campo": campo, "mensagem": "O texto não pode conter o caractere nulo."}
    ]


@pytest.mark.parametrize("recurso", ["eleitores", "candidatos"])
def test_caractere_nulo_no_filtro_por_nome_responde_422(cliente, cabecalho_chefe, recurso):
    """RN-20 / RN-30: o filtro `nome` com caractere nulo é recusado (422), não vira 500."""
    resposta = cliente.get(f"/api/v1/{recurso}", params={"nome": "a\x00b"}, headers=cabecalho_chefe)

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["detalhes"]["campos"][0]["campo"] == "nome"


def test_erro_do_banco_nao_leva_os_valores_do_sql():
    """Seção 7: a mensagem de erro do banco (que vai para o log do 500) não traz os parâmetros.

    Sem `hide_parameters`, o SQLAlchemy põe os valores na mensagem (ex.: hash da senha e CPF).
    """
    segredo = "$2b$12$hash-que-nao-pode-ir-para-o-log"

    with SessionLocal() as sessao, pytest.raises(DBAPIError) as erro:
        sessao.execute(
            text("SELECT CAST(:numero AS SMALLINT), :segredo"),
            {"numero": 99_999, "segredo": segredo},
        )

    assert "smallint out of range" in str(erro.value)
    assert segredo not in str(erro.value)
