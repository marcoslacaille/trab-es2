"""A especificação publicada está atualizada e as rotas documentam 401 e 403."""

import json
import re

from app.main import app
from app.models.enums import Perfil
from app.scripts.exportar_openapi import CAMINHO_OPENAPI
from tests.arquitetura.test_rotas_protegidas import LISTA_BRANCA, rotas_da_api
from tests.integracao.test_permissoes import ROTAS, TODOS

PREFIXO = "/api/v1"


def _normalizar(caminho: str) -> str:
    """Troca ids de exemplo (`/eleicoes/1`) e parâmetros (`/eleicoes/{eleicao_id}`) por `{}`."""
    return re.sub(r"/(\d+|\{[^}]+\})", "/{}", caminho)


def _perfis_restritos() -> set[tuple[str, str]]:
    """(método, caminho) das rotas que a tabela `ROTAS` limita a menos de todos os perfis."""
    return {(m, _normalizar(PREFIXO + c)) for m, c, perfis in ROTAS if perfis != TODOS}


def _respostas_documentadas() -> dict[tuple[str, str], set[int]]:
    esquema = app.openapi()
    return {
        (metodo.upper(), _normalizar(caminho)): {int(codigo) for codigo in operacao["responses"]}
        for caminho, operacoes in esquema["paths"].items()
        for metodo, operacao in operacoes.items()
    }


def test_rotas_protegidas_documentam_401_e_403():
    """RN-03: rotas fora da lista branca têm 401 em `responses`; as restritas a perfis, 403."""
    usados = {perfil for _, _, perfis in ROTAS for perfil in perfis}
    assert usados <= set(Perfil)  # a tabela só cita Chefe, Eleitor e Candidato

    documentadas = _respostas_documentadas()
    sem_401 = [
        f"{metodo} {rota.path}"
        for rota in rotas_da_api()
        if rota.path not in LISTA_BRANCA
        for metodo in sorted(rota.metodos)
        if 401 not in documentadas[(metodo, _normalizar(rota.path))]
    ]
    sem_403 = [
        f"{metodo} {caminho}"
        for metodo, caminho in sorted(_perfis_restritos())
        if 403 not in documentadas[(metodo, caminho)]
    ]

    assert sem_401 == []
    assert sem_403 == []


def test_especificacao_publicada_esta_atualizada():
    """`docs/openapi.json` (usado pelo GitHub Pages) é igual a `app.openapi()`."""
    publicada = json.loads(CAMINHO_OPENAPI.read_text(encoding="utf-8"))

    assert publicada == app.openapi(), "Rode python -m app.scripts.exportar_openapi"
