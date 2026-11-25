"""TI-08 / RN-03, RN-06: matriz de permissões de todas as rotas protegidas."""

import pytest

from app.models.enums import Perfil

PREFIXO = "/api/v1"
C, E, K = Perfil.CHEFE_SECAO, Perfil.ELEITOR, Perfil.CANDIDATO
TODOS = {C, E, K}

# (método, caminho com ids de exemplo, perfis permitidos). Rotas "Todos" não têm perfil proibido,
# então só entram no teste de 401.
ROTAS = [
    ("GET", "/auth/me", TODOS),
    ("POST", "/eleicoes", {C}),
    ("GET", "/eleicoes", TODOS),
    ("GET", "/eleicoes/1", TODOS),
    ("PATCH", "/eleicoes/1", {C}),
    ("POST", "/eleicoes/1/abertura", {C}),
    ("POST", "/eleicoes/1/encerramento", {C}),
    ("GET", "/eleicoes/1/candidaturas", {C}),
    ("POST", "/eleicoes/1/candidaturas", {C}),
    ("PATCH", "/eleicoes/1/candidaturas/1", {C}),
    ("DELETE", "/eleicoes/1/candidaturas/1", {C}),
    ("GET", "/candidaturas/minhas", {K}),
    ("POST", "/eleitores", {C}),
    ("GET", "/eleitores", {C}),
    ("GET", "/eleitores/eu", {E}),
    ("GET", "/eleitores/1", {C}),
    ("PATCH", "/eleitores/1", {C}),
    ("DELETE", "/eleitores/1", {C}),
    ("POST", "/candidatos", {C}),
    ("GET", "/candidatos", {C}),
    ("GET", "/candidatos/eu", {K}),
    ("GET", "/candidatos/1", {C}),
    ("PATCH", "/candidatos/1", {C}),
    ("DELETE", "/candidatos/1", {C}),
    ("POST", "/partidos", {C}),
    ("GET", "/partidos", TODOS),
    ("GET", "/votacao/eleicoes/1/cedula", {E}),
    ("POST", "/votacao/eleicoes/1/votos/registro", {E}),
    ("POST", "/votacao/eleicoes/1/votos/confirmacao", {E}),
    ("GET", "/votacao/eleicoes/1/participacao", {E}),
    ("GET", "/apuracao/eleicoes/1/parcial", {C, E, K}),
    ("GET", "/apuracao/eleicoes/1/resultado", TODOS),
]

ROTAS_RESTRITAS = [(m, c, p) for m, c, p in ROTAS if p != TODOS]


def _chamar(cliente, metodo, caminho, cabecalho=None):
    # Corpo vazio basta: a permissão é conferida antes da validação do corpo.
    return cliente.request(metodo, PREFIXO + caminho, headers=cabecalho or {}, json={})


def test_ti08_tabela_cobre_as_32_rotas_protegidas():
    """TI-08: a tabela do teste tem as 32 rotas protegidas (33 menos o login)."""
    assert len(ROTAS) == 32
    assert len(set((m, c) for m, c, _ in ROTAS)) == 32


@pytest.mark.parametrize(("metodo", "caminho", "permitidos"), ROTAS)
def test_ti08_sem_token_responde_401(cliente, metodo, caminho, permitidos):
    """TI-08 / RN-06: toda rota protegida sem token responde 401 `NAO_AUTENTICADO`."""
    resposta = _chamar(cliente, metodo, caminho)

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "NAO_AUTENTICADO"


@pytest.mark.parametrize(("metodo", "caminho", "permitidos"), ROTAS_RESTRITAS)
def test_ti08_perfil_nao_permitido_responde_403(
    cliente, cabecalho_chefe, cabecalho_eleitor, cabecalho_candidato, metodo, caminho, permitidos
):
    """TI-08 / RN-03: cada perfil fora da lista da rota recebe 403 `PERFIL_NAO_AUTORIZADO`."""
    cabecalhos = {C: cabecalho_chefe, E: cabecalho_eleitor, K: cabecalho_candidato}

    for perfil in TODOS - permitidos:
        resposta = _chamar(cliente, metodo, caminho, cabecalhos[perfil])

        assert resposta.status_code == 403, f"{perfil}: {resposta.text}"
        assert resposta.json()["erro"]["codigo"] == "PERFIL_NAO_AUTORIZADO"
