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
# `dominio.py` e no `servico.py`, e só nas arestas do grafo.
# D-103: todo `servico.py` recebe o `UsuarioAutenticado` da rota (assinaturas da seção 9), então
# `app.identidade.dominio` (só tipos) também vale para módulos sem aresta para `identidade`.


def _importacoes(arquivo: Path) -> list[str]:
    """Nomes completos importados pelo arquivo (`from app.x import y` vira `app.x.y`)."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes += [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes += [f"{no.module}.{alias.name}" for alias in no.names]
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
    return importado.startswith("app.identidade.dominio.") and arquivo.name in (
        "dominio.py",
        "servico.py",
    )


def _violacoes_de_fronteira() -> list[str]:
    problemas = []
    for modulo, arquivo in _arquivos_dos_modulos():
        for importado in _importacoes(arquivo):
            outro, camada = _destino(importado)
            if outro is None or outro in (modulo, "compartilhado"):
                continue
            onde = f"{arquivo.relative_to(RAIZ.parent)} importa {importado}"
            if _tipo_de_identidade(importado, arquivo):
                continue  # D-103
            if outro not in MODULOS or outro not in ARESTAS[modulo] | {"identidade"}:
                problemas.append(onde + " (aresta fora do grafo)")
            elif outro == "identidade" and camada == "dependencias":
                if arquivo.name != "rotas.py":
                    problemas.append(onde + " (dependencias só nas rotas)")
            elif outro not in ARESTAS[modulo]:
                problemas.append(onde + " (aresta fora do grafo)")
            elif camada == "servico":
                continue
            elif camada == "dominio" and arquivo.name in ("dominio.py", "servico.py"):
                continue  # D-077 / D-098
            else:
                problemas.append(onde + " (só `servico` de outro módulo)")
    return problemas


def test_ta01_modulos_so_importam_o_que_o_grafo_permite():
    """TA-01 / RN-03: só `servico` (e `dominio` como tipo, D-077) dos módulos vizinhos."""
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
def test_ta01_servico_nao_importa_rotas_nem_fastapi(modulo):
    """TA-01: `servico.py` não importa `rotas` nem FastAPI (seção 5, tabela de camadas)."""
    for importado in _importacoes(RAIZ / modulo / "servico.py"):
        assert importado.split(".")[0] != "fastapi", importado
        assert not importado.startswith(f"app.{modulo}.rotas"), importado


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_rotas_nao_importam_repositorio_nem_modelos(modulo):
    """TA-01: `rotas.py` não importa `repositorio` nem `modelos` (nem de outro módulo)."""
    for importado in _importacoes(RAIZ / modulo / "rotas.py"):
        _, camada = _destino(importado)
        assert camada not in ("repositorio", "modelos"), importado


def test_ta01_detecta_violacao_de_fronteira(tmp_path):
    """TA-01: o verificador de fato enxerga uma importação proibida (teste do teste)."""
    arquivo = tmp_path / "servico.py"
    arquivo.write_text("from app.eleitores.repositorio import buscar\nimport app.votacao.modelos\n")

    assert _importacoes(arquivo) == ["app.eleitores.repositorio.buscar", "app.votacao.modelos"]
    assert _destino("app.eleitores.repositorio.buscar") == ("eleitores", "repositorio")
