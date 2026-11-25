"""TA-02 / RN-06: toda rota fora da lista branca depende de `obter_usuario_atual`."""

from dataclasses import dataclass

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, _IncludedRouter

from app.dependencies import obter_usuario_atual
from app.main import app

# Rotas públicas: saúde, login e a documentação (que o FastAPI registra como rotas simples).
LISTA_BRANCA = {"/health", "/api/v1/auth/login"}


def _depende_de(dependente: Dependant, funcao) -> bool:
    """Procura `funcao` na árvore de dependências (inclusive as aninhadas, como `exige_perfil`)."""
    return any(sub.call is funcao or _depende_de(sub, funcao) for sub in dependente.dependencies)


@dataclass
class RotaDaApi:
    metodos: set[str]
    path: str  # caminho completo, com o prefixo `/api/v1`
    dependant: Dependant


def rotas_da_api() -> list[RotaDaApi]:
    """Todas as `APIRoute` do app, já com o prefixo.

    O FastAPI 0.165 guarda cada `include_router` como um `_IncludedRouter` que só monta as rotas
    efetivas (com prefixo) sob demanda; por isso o teste desce por `effective_route_contexts`.
    """
    rotas = []
    for rota in app.routes:
        if isinstance(rota, _IncludedRouter):
            for contexto in rota.effective_route_contexts():
                original = contexto.original_route
                rotas.append(RotaDaApi(original.methods, contexto.path, original.dependant))
        elif isinstance(rota, APIRoute):
            rotas.append(RotaDaApi(rota.methods, rota.path, rota.dependant))
    return rotas


def test_ta02_toda_rota_fora_da_lista_branca_exige_usuario_atual():
    """TA-02 / RN-06: a árvore de dependências de cada rota protegida tem `obter_usuario_atual`."""
    sem_protecao = [
        f"{sorted(rota.metodos)} {rota.path}"
        for rota in rotas_da_api()
        if rota.path not in LISTA_BRANCA and not _depende_de(rota.dependant, obter_usuario_atual)
    ]

    assert sem_protecao == []


def test_ta02_lista_branca_so_tem_rotas_que_existem():
    """TA-02: a lista branca não guarda caminho que já não existe (evita exceção esquecida)."""
    caminhos = {rota.path for rota in rotas_da_api()}

    assert caminhos >= LISTA_BRANCA


def test_ta02_app_tem_33_rotas_de_negocio_mais_health():
    """TA-02: 33 rotas sob `/api/v1` mais `/health` (seção 10); nenhuma rota some sem aviso."""
    caminhos = [rota.path for rota in rotas_da_api()]

    assert len([c for c in caminhos if c.startswith("/api/v1")]) == 33
    assert "/health" in caminhos
