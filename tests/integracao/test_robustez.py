"""Entradas no limite: nenhuma delas pode virar erro 500.

Achados do teste de caixa-preta contra a API real: ID maior que o
BIGINT do PostgreSQL, caractere nulo em campo de texto, valores do SQL no log de erro e página
cujo deslocamento (OFFSET) passa do BIGINT.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import obter_configuracao
from app.core.database import SessionLocal
from app.core.paginacao import MAIOR_PAGINA, TAMANHO_MAXIMO
from app.core.security import ALGORITMO, AUDIENCIA_ACESSO
from tests.auxiliares import nova_eleicao, novo_candidato, novo_eleitor, novo_partido

ID_GIGANTE = 10**20  # maior que 9.223.372.036.854.775.807 (BIGINT)


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def test_id_ou_token_fora_da_faixa_do_bigint_nao_vira_500(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-02 e RN-46: ID fora da faixa do BIGINT (caminho, corpo ou `sub` do token) não vira 500."""
    caminhos = [
        f"/api/v1/eleicoes/{ID_GIGANTE}",
        f"/api/v1/eleitores/{ID_GIGANTE}",
        f"/api/v1/candidatos/{ID_GIGANTE}",
        f"/api/v1/eleicoes/1/candidaturas/{ID_GIGANTE}",
        f"/api/v1/apuracao/eleicoes/{ID_GIGANTE}/parcial",
        f"/api/v1/apuracao/eleicoes/{ID_GIGANTE}/resultado",
    ]
    for caminho in caminhos:
        metodo = "DELETE" if "candidaturas" in caminho else "GET"

        resposta = cliente.request(metodo, caminho, headers=cabecalho_chefe)

        assert resposta.status_code == 422, caminho
        assert _codigo(resposta) == "DADOS_INVALIDOS", caminho

    cedula = cliente.get(f"/api/v1/votacao/eleicoes/{ID_GIGANTE}/cedula", headers=cabecalho_eleitor)
    assert cedula.status_code == 422

    eleicao_id = nova_eleicao(cliente, cabecalho_chefe).json()["id"]
    partido_id = novo_partido(cliente, cabecalho_chefe).json()["id"]
    candidatura = cliente.post(
        f"/api/v1/eleicoes/{eleicao_id}/candidaturas",
        json={
            "candidato_id": ID_GIGANTE,
            "partido_id": partido_id,
            "cargo": "GOVERNADOR",
            "numero": "11",
        },
        headers=cabecalho_chefe,
    )
    assert candidatura.status_code == 422
    assert _codigo(candidatura) == "DADOS_INVALIDOS"

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
    com_token = cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert com_token.status_code == 401
    assert _codigo(com_token) == "TOKEN_INVALIDO"


def test_caractere_nulo_responde_422(cliente, cabecalho_chefe):
    """RN-08, RN-20 e RN-30: texto ou filtro com o caractere nulo dá 422 no esquema, não 500."""
    cadastros = [
        (novo_eleitor, "nome"),
        (novo_candidato, "nome"),
        (novo_candidato, "nome_urna"),
        (novo_partido, "nome"),
        (nova_eleicao, "descricao"),
    ]
    for cadastrar, campo in cadastros:
        resposta = cadastrar(cliente, cabecalho_chefe, **{campo: "Ana\x00Maria"})

        assert resposta.status_code == 422, campo
        assert resposta.json()["erro"]["detalhes"]["campos"] == [
            {"campo": campo, "mensagem": "O texto não pode conter o caractere nulo."}
        ]

    for recurso in ("eleitores", "candidatos"):
        filtro = cliente.get(
            f"/api/v1/{recurso}", params={"nome": "a\x00b"}, headers=cabecalho_chefe
        )

        assert filtro.status_code == 422, recurso
        assert filtro.json()["erro"]["detalhes"]["campos"][0]["campo"] == "nome"


def test_limites_da_paginacao(cliente, cabecalho_chefe):
    """`pagina` cujo deslocamento passa do BIGINT dá 422 (antes era 500); a última aceita cabe."""
    for recurso in ("eleitores", "candidatos"):
        for pagina in (MAIOR_PAGINA + 1, 2**62, ID_GIGANTE):
            resposta = cliente.get(
                f"/api/v1/{recurso}", params={"pagina": pagina}, headers=cabecalho_chefe
            )

            assert resposta.status_code == 422, (recurso, pagina)
            assert _codigo(resposta) == "DADOS_INVALIDOS", (recurso, pagina)
            assert resposta.json()["erro"]["detalhes"]["campos"][0]["campo"] == "pagina"

        ultima = cliente.get(
            f"/api/v1/{recurso}",
            params={"pagina": MAIOR_PAGINA, "tamanho": TAMANHO_MAXIMO},
            headers=cabecalho_chefe,
        )

        assert ultima.status_code == 200, recurso
        assert ultima.json()["itens"] == []
        assert ultima.json()["pagina"] == MAIOR_PAGINA


def test_erro_do_banco_nao_leva_os_valores_do_sql():
    """A mensagem de erro do banco (que vai para o log do 500) não traz os parâmetros.

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
