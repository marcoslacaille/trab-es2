"""TA-01 / RN-03: fronteiras entre módulos (seção 5 do PLANO), verificadas com `ast`."""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "app"
MODULOS = ["identidade", "eleitores", "candidatos", "eleicoes", "votacao", "apuracao"]

# Arestas permitidas: exatamente o grafo da seção 5.
ARESTAS = {
    "identidade": set(),
    "eleitores": {"identidade"},
    "candidatos": {"identidade"},
    "eleicoes": {"candidatos"},
    "votacao": {"eleicoes", "eleitores"},
    "apuracao": {"votacao", "eleicoes", "eleitores"},
}

# D-077 e D-098: `dominio` de outro módulo (só tipos: dataclasses e enums) pode ser importado no
# `dominio.py` e no `service.py`, e só nas arestas do grafo.
# D-103: todo `service.py` recebe o `UsuarioAutenticado` da rota (assinaturas da seção 9), então
# `app.identidade.dominio` (só tipos) também vale para módulos sem aresta para `identidade`.
# D-148: desses tipos, só `Perfil` e `UsuarioAutenticado`; funções de identidade só pelo serviço.
TIPOS_DE_IDENTIDADE = {
    "app.identidade.dominio.Perfil",
    "app.identidade.dominio.UsuarioAutenticado",
}


def _importacoes(arquivo: Path) -> list[str]:
    """Nomes completos importados pelo arquivo (`from app.x import y` vira `app.x.y`).

    Import relativo (`from ..x import y`) volta com os pontos na frente (`..x.y`), para o
    verificador acusar: nele o destino não fica claro e a fronteira passaria sem conferência.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes += [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom):
            origem = "." * no.level + (no.module or "")
            nomes += [f"{origem}.{alias.name}" for alias in no.names]
    return nomes


def _arquivos_dos_modulos() -> list[tuple[str, Path]]:
    return [(m, a) for m in MODULOS for a in sorted((RAIZ / m).glob("*.py"))]


def _destino(importado: str) -> tuple[str | None, str | None]:
    """Devolve (módulo, arquivo) de um `app.<modulo>.<arquivo>...`, ou (None, None)."""
    partes = importado.split(".")
    if partes[0] != "app" or len(partes) < 2:
        return None, None
    return partes[1], partes[2] if len(partes) > 2 else None


def _tipo_de_identidade(importado: str, arquivo: Path) -> bool:
    return importado in TIPOS_DE_IDENTIDADE and arquivo.name in ("dominio.py", "service.py")


def _violacoes_no_arquivo(modulo: str, arquivo: Path) -> list[str]:
    """As importações de um arquivo do `modulo` que quebram as fronteiras da seção 5."""
    problemas = []
    for importado in _importacoes(arquivo):
        onde = f"app/{modulo}/{arquivo.name} importa {importado}"
        if importado.startswith("."):
            problemas.append(onde + " (import relativo: use `app.<modulo>`)")
            continue
        outro, camada = _destino(importado)
        if outro is None or outro in (modulo, "compartilhado"):
            continue
        if _tipo_de_identidade(importado, arquivo):
            continue  # D-103
        if outro not in MODULOS or outro not in ARESTAS[modulo] | {"identidade"}:
            problemas.append(onde + " (aresta fora do grafo)")
        elif outro == "identidade" and camada == "dependencias":
            if arquivo.name != "controller.py":
                problemas.append(onde + " (dependencias só nas rotas)")
        elif outro not in ARESTAS[modulo]:
            problemas.append(onde + " (aresta fora do grafo)")
        elif camada == "service":
            continue
        elif camada == "dominio" and arquivo.name in ("dominio.py", "service.py"):
            continue  # D-077 / D-098
        else:
            problemas.append(onde + " (só `service` de outro módulo)")
    return problemas


def _violacoes_de_fronteira() -> list[str]:
    return [
        problema
        for modulo, arquivo in _arquivos_dos_modulos()
        for problema in _violacoes_no_arquivo(modulo, arquivo)
    ]


def test_ta01_modulos_so_importam_o_que_o_grafo_permite():
    """TA-01 / RN-03: só `service` (e `dominio` como tipo, D-077) dos módulos vizinhos."""
    assert _violacoes_de_fronteira() == []


def test_ta01_nao_ha_ciclos_entre_modulos():
    """TA-01: o grafo de dependências reais não tem ciclo."""
    reais = {m: set() for m in MODULOS}
    for modulo, arquivo in _arquivos_dos_modulos():
        for importado in _importacoes(arquivo):
            outro, _ = _destino(importado)
            if outro in MODULOS and outro != modulo:
                reais[modulo].add(outro)

    visitados, pilha = set(), []

    def visitar(no: str):
        assert no not in pilha, f"ciclo: {pilha + [no]}"
        if no in visitados:
            return
        pilha.append(no)
        for vizinho in reais[no]:
            visitar(vizinho)
        pilha.pop()
        visitados.add(no)

    for modulo in MODULOS:
        visitar(modulo)


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_dominio_nao_importa_fastapi_nem_sqlalchemy(modulo):
    """TA-01: `dominio.py` não importa `fastapi` nem `sqlalchemy` (regra de dependência)."""
    for importado in _importacoes(RAIZ / modulo / "dominio.py"):
        assert importado.split(".")[0] not in ("fastapi", "sqlalchemy"), importado


def test_ta01_dominio_compartilhado_nao_importa_fastapi_nem_sqlalchemy():
    """TA-01: o núcleo compartilhado também fica livre de framework e banco."""
    for importado in _importacoes(RAIZ / "compartilhado" / "dominio.py"):
        assert importado.split(".")[0] not in ("fastapi", "sqlalchemy"), importado


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_service_nao_importa_controller_nem_fastapi(modulo):
    """TA-01: `service.py` não importa `controller` nem FastAPI (seção 5, tabela de camadas)."""
    for importado in _importacoes(RAIZ / modulo / "service.py"):
        assert importado.split(".")[0] != "fastapi", importado
        assert not importado.startswith(f"app.{modulo}.controller"), importado


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_controller_nao_importa_repository_nem_model(modulo):
    """TA-01: `controller.py` não importa `repository` nem `model` (nem de outro módulo)."""
    for importado in _importacoes(RAIZ / modulo / "controller.py"):
        _, camada = _destino(importado)
        assert camada not in ("repository", "model"), importado


def test_ta01_detecta_violacao_de_fronteira(tmp_path):
    """TA-01: o verificador de fato acusa cada importação proibida (teste do teste, D-148)."""
    arquivo = tmp_path / "service.py"
    arquivo.write_text(
        "from app.eleitores.repository import buscar\n"  # camada errada do vizinho
        "from app.candidatos.service import listar\n"  # aresta que o grafo não tem
        "from ..eleicoes import repository\n"  # import relativo
        "from app.identidade.dominio import validar_senha\n"  # função, não tipo
        "from app.eleicoes.service import obter_eleicao\n"  # permitido
        "from app.identidade.dominio import UsuarioAutenticado\n"  # permitido (D-103)
        "import app.votacao.model\n"  # o próprio módulo: permitido
    )

    assert _violacoes_no_arquivo("votacao", arquivo) == [
        "app/votacao/service.py importa app.eleitores.repository.buscar"
        " (só `service` de outro módulo)",
        "app/votacao/service.py importa app.candidatos.service.listar (aresta fora do grafo)",
        "app/votacao/service.py importa ..eleicoes.repository"
        " (import relativo: use `app.<modulo>`)",
        "app/votacao/service.py importa app.identidade.dominio.validar_senha"
        " (aresta fora do grafo)",
    ]


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_dominio_nao_importa_repository_nem_model(modulo):
    """TA-01 / D-148: `dominio.py` só tem regras puras; não lê o banco nem do próprio módulo."""
    for importado in _importacoes(RAIZ / modulo / "dominio.py"):
        _, camada = _destino(importado)
        assert camada not in ("repository", "model"), importado


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_schemas_nao_importam_sqlalchemy(modulo):
    """TA-01 / D-148: `schemas.py` é o contrato HTTP; não conhece o banco."""
    for importado in _importacoes(RAIZ / modulo / "schemas.py"):
        assert importado.split(".")[0] != "sqlalchemy", importado
