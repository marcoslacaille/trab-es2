"""Log de requisições: método, caminho, status e duração, sem dados sensíveis."""

import logging

from fastapi.testclient import TestClient

from app.core.database import obter_sessao
from app.main import app
from tests.auxiliares import CPF_CHEFE, SENHA_CHEFE, criar_chefe

NOME_DO_LOG = "eleicao.requisicoes"


def test_registra_metodo_caminho_status_e_duracao(cliente, caplog):
    """Cada requisição gera uma linha com método, caminho, status e duração em ms."""
    with caplog.at_level(logging.INFO, logger=NOME_DO_LOG):
        cliente.get("/health")

    linhas = [r.getMessage() for r in caplog.records if r.name == NOME_DO_LOG]
    assert len(linhas) == 1
    assert linhas[0].startswith("GET /health -> 200 (") and linhas[0].endswith(" ms)")


def test_nao_registra_corpo_token_senha_nem_query(cliente, caplog):
    """RN-60: login e consulta com query não deixam senha, token, CPF nem query no log."""
    criar_chefe()
    with caplog.at_level(logging.DEBUG):
        login = cliente.post(
            "/api/v1/auth/login", data={"username": CPF_CHEFE, "password": SENHA_CHEFE}
        )
        token = login.json()["access_token"]
        cliente.get(
            "/api/v1/eleitores?nome=Fulano",
            headers={"Authorization": f"Bearer {token}"},
        )

    # Só o log do servidor: o httpx do cliente de teste também loga a URL completa.
    texto = "\n".join(f"{r.getMessage()} {r.args}" for r in caplog.records if r.name == NOME_DO_LOG)
    assert "POST /api/v1/auth/login -> 200" in texto
    assert "GET /api/v1/eleitores -> 200" in texto
    for segredo in (SENHA_CHEFE, CPF_CHEFE, token, "Fulano", "Bearer", "nome="):
        assert segredo not in texto


def test_registra_status_de_erro(cliente, caplog):
    """Respostas de erro também são logadas, com o status delas."""
    with caplog.at_level(logging.INFO, logger=NOME_DO_LOG):
        cliente.get("/api/v1/auth/me")

    assert "GET /api/v1/auth/me -> 401" in caplog.text


def test_registra_status_500_quando_a_rota_falha(caplog):
    """Erro interno também é logado, com status 500 (e a resposta não vaza detalhes)."""

    def sessao_quebrada():
        raise RuntimeError("segredo interno")

    app.dependency_overrides[obter_sessao] = sessao_quebrada
    try:
        with caplog.at_level(logging.INFO, logger=NOME_DO_LOG):
            resposta = TestClient(app, raise_server_exceptions=False).get("/health")
    finally:
        app.dependency_overrides.pop(obter_sessao, None)

    assert resposta.status_code == 500 and "segredo interno" not in resposta.text
    assert "GET /health -> 500" in caplog.text
