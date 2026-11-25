"""Teste de arquitetura por camada, lendo o código de `app/` com `ast`.

Cada arquivo de `app/` é classificado pela pasta e pelo nome (`services/eleitor_service.py` é o
service do assunto `eleitor`), e os imports dele são conferidos contra estas regras:

- direção das camadas: o que cada pasta pode importar (`PODE_IMPORTAR`);
- grafo entre os services: só as arestas de `GRAFO`, sem ciclo;
- fronteira do assunto: cada arquivo só importa o próprio assunto, e cada service usa só o
  próprio repository e os models do próprio assunto;
- ocultação de informação: `core/security.py` e `core/cedula.py` só têm quem os importe por dever;
- `dto/` e `models/enums.py` sem framework;
- services e repositories não chegam ao FastAPI nem indiretamente, pelos módulos que importam;
- nenhum import relativo.

Os testes do próprio verificador ficam no fim do arquivo.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "app"
BASE = RAIZ.parent

# Mapa de camadas --------------------------------------------------------------------------------

# Pasta -> sufixo dos arquivos dela (`<assunto>_<sufixo>.py`); `models/` e `core/` não têm sufixo.
SUFIXOS = {
    "controllers": "_controller",
    "services": "_service",
    "repositories": "_repository",
    "schemas": "_schema",
    "dto": "_dto",
    "models": "",
    "core": "",
}

# Nome do arquivo (sem pasta, sem `.py` e sem sufixo) -> assunto. Um assunto é um service: a
# candidatura é parte da eleição, o login é do usuário, e o registro de votação e o voto são da
# votação.
ASSUNTO_DO_ARQUIVO = {
    "usuario": "usuario",
    "auth": "usuario",
    "eleitor": "eleitor",
    "candidato": "candidato",
    "partido": "partido",
    "eleicao": "eleicao",
    "candidatura": "eleicao",
    "votacao": "votacao",
    "registro_votacao": "votacao",
    "voto": "votacao",
    "apuracao": "apuracao",
}

_ASSUNTOS_DOS_DADOS = {
    "usuario",
    "eleitor",
    "candidato",
    "partido",
    "eleicao",
    "candidatura",
    "votacao",
    "apuracao",
}

# Arquivos que cada pasta precisa ter. Só a apuração não guarda dados (sem repository nem model).
ARQUIVOS_ESPERADOS = {
    "controllers": {"auth", "candidatura", *(_ASSUNTOS_DOS_DADOS - {"usuario"})},
    "services": _ASSUNTOS_DOS_DADOS - {"candidatura"},
    "repositories": _ASSUNTOS_DOS_DADOS - {"candidatura", "apuracao"},
    "schemas": _ASSUNTOS_DOS_DADOS,
    "dto": _ASSUNTOS_DOS_DADOS,
    "models": {
        "enums",
        "registro_votacao",
        "voto",
        *(_ASSUNTOS_DOS_DADOS - {"votacao", "apuracao"}),
    },
    "core": {
        "cedula",
        "config",
        "database",
        "exceptions",
        "log_requisicoes",
        "openapi",
        "paginacao",
        "relogio",
        "security",
        "validadores",
        "web",
    },
}


@dataclass(frozen=True)
class Local:
    """Onde mora um arquivo de `app/`: a camada, o arquivo (sem pasta, `.py` e sufixo) e o assunto.

    Camadas: `controllers`, `services`, `repositories`, `schemas`, `dto`, `models` (tabelas),
    `enums`, `core`, `dependencies` e `raiz` (`main`, `scripts` e os `__init__.py`).
    """

    camada: str
    arquivo: str | None = None
    assunto: str | None = None

    @property
    def rotulo(self) -> str:
        """Como as regras chamam o destino: `core.security` no `core`, a camada nas outras."""
        return f"core.{self.arquivo}" if self.camada == "core" and self.arquivo else self.camada


def _local(nome: str) -> Local | None:
    """Classifica um nome como `app.services.eleitor_service.EleitorService`.

    Devolve `None` para o que não é de `app` (biblioteca padrão, fastapi...). O que está em `app/`
    mas fora do mapa levanta `ValueError`: melhor falhar do que deixar um arquivo sem regra.
    """
    partes = nome.split(".")
    if partes[0] != "app" or len(partes) < 2:
        return None
    pasta, arquivo = partes[1], (partes[2] if len(partes) > 2 else None)

    if pasta == "dependencies":
        return Local("dependencies")
    if pasta == "core":
        return Local("core", arquivo)
    if pasta in SUFIXOS:
        if arquivo in (None, "__init__"):
            return Local("raiz")
        if pasta == "models" and arquivo == "enums":
            return Local("enums")
        sem_sufixo = arquivo.removesuffix(SUFIXOS[pasta])
        if arquivo.endswith(SUFIXOS[pasta]) and sem_sufixo in ARQUIVOS_ESPERADOS[pasta]:
            return Local(pasta, sem_sufixo, ASSUNTO_DO_ARQUIVO[sem_sufixo])
    elif pasta in ("main", "scripts", "__init__"):
        return Local("raiz")
    raise ValueError(f"sem classificação no mapa de camadas: {nome}")


# Regras -----------------------------------------------------------------------------------------

# O que cada camada pode importar de `app/` (coluna "Pode importar" da tabela de dependências).
# Tudo que não está na lista é proibido, inclusive `main` e `scripts`, que ninguém importa.
PODE_IMPORTAR = {
    "controllers": {"dependencies", "services", "schemas", "dto", "enums", "core"},
    "services": {"repositories", "services", "dto", "models", "enums", "core"},
    "repositories": {"models", "dto", "enums", "core"},
    "schemas": {"dto", "enums", "core"},
    "dto": {"dto", "enums"},
    "models": {"enums", "core.database", "core.validadores"},
    "enums": {"core.validadores"},
    "core": {"core", "enums"},
    "core.cedula": {"core", "enums", "dto"},  # só a cédula conhece o DTO da votação
}

# Bibliotecas que cada camada não pode importar (coluna "Não pode importar"). `dto/` e
# `models/enums.py` têm regra própria, mais rígida: nenhum dos três frameworks.
SEM_FRAMEWORK = {
    "controllers": {"sqlalchemy"},
    "services": {"fastapi"},
    "repositories": {"fastapi"},
    "schemas": {"sqlalchemy"},
    "models": {"fastapi"},
}
FRAMEWORKS_DOS_DADOS = {"fastapi", "pydantic", "sqlalchemy"}

# O que services e repositories não alcançam nem indiretamente: a regra vale também para os
# módulos de `app/` que eles importam, e para os que esses importam (por isso o que é do FastAPI
# em `core/` fica em `core/web.py`, que nenhum dos dois importa).
SEM_FRAMEWORK_NEM_INDIRETO = {
    "services": {"fastapi", "starlette"},
    "repositories": {"fastapi", "starlette"},
}

# Grafo entre os services: de quem cada um pode depender.
GRAFO = {
    "usuario": set(),
    "partido": set(),
    "eleitor": {"usuario"},
    "candidato": {"usuario"},
    "eleicao": {"candidato", "partido"},
    "votacao": {"eleicao", "eleitor"},
    "apuracao": {"votacao", "eleicao", "eleitor"},
}

# O `UsuarioAutenticado` chega a todo service como parâmetro, então qualquer service o importa.
USUARIO_AUTENTICADO = "app.dto.usuario_dto.UsuarioAutenticado"

Regra = Callable[..., list[str]]


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


def _importacoes_de_app(arquivo: Path) -> list[tuple[str, Local]]:
    """Cada import absoluto de `app` do arquivo, com a classificação do destino."""
    achados = []
    for importado in _importacoes(arquivo):
        destino = None if importado.startswith(".") else _local(importado)
        if destino is not None:
            achados.append((importado, destino))
    return achados


def _origem(arquivo: Path, base: Path = BASE) -> Local:
    """`base/app/services/eleitor_service.py` -> `Local("services", "eleitor", "eleitor")`."""
    return _local(arquivo.relative_to(base).with_suffix("").as_posix().replace("/", "."))


def _onde(arquivo: Path, base: Path, importado: str) -> str:
    return f"{arquivo.relative_to(base).as_posix()} importa {importado}"


def _direcao(arquivo: Path, base: Path = BASE) -> list[str]:
    """Imports que a camada do arquivo não pode ter (`PODE_IMPORTAR` e `SEM_FRAMEWORK`)."""
    origem = _origem(arquivo, base)
    chave = origem.rotulo if origem.rotulo in PODE_IMPORTAR else origem.camada
    permitidos = PODE_IMPORTAR.get(chave)
    if permitidos is None:  # `dependencies.py` e a raiz de composição não têm regra de direção
        return []
    problemas = []
    for importado in _importacoes(arquivo):
        if importado.startswith("."):
            continue
        biblioteca = importado.split(".")[0]
        if biblioteca in SEM_FRAMEWORK.get(origem.camada, ()):
            motivo = f"{origem.camada} não importa {biblioteca}"
            problemas.append(f"{_onde(arquivo, base, importado)} ({motivo})")
        destino = _local(importado)
        if destino is not None and not {destino.rotulo, destino.camada} & permitidos:
            motivo = f"{origem.camada} não importa {destino.rotulo}"
            problemas.append(f"{_onde(arquivo, base, importado)} ({motivo})")
    return problemas


def _fora_do_grafo(arquivo: Path, base: Path = BASE) -> list[str]:
    """Service que importa um service de que o grafo não o deixa depender."""
    origem = _origem(arquivo, base)
    if origem.camada != "services":
        return []
    return [
        f"{_onde(arquivo, base, importado)} (aresta fora do grafo: "
        f"{origem.assunto} não depende de {destino.assunto})"
        for importado, destino in _importacoes_de_app(arquivo)
        if destino.camada == "services"
        and destino.assunto != origem.assunto
        and destino.assunto not in GRAFO[origem.assunto]
    ]


def _repository_ou_model_de_outro_assunto(arquivo: Path, base: Path = BASE) -> list[str]:
    """Service que usa o repository ou um model que não é do próprio assunto."""
    origem = _origem(arquivo, base)
    if origem.camada != "services":
        return []
    return [
        f"{_onde(arquivo, base, importado)} "
        f"(o service de {origem.assunto} usa {destino.camada} de {destino.assunto})"
        for importado, destino in _importacoes_de_app(arquivo)
        if destino.camada in ("repositories", "models") and destino.assunto != origem.assunto
    ]


def _dto_de_outro_assunto_fora_do_grafo(arquivo: Path, base: Path = BASE) -> list[str]:
    """Service ou DTO que importa o DTO de um assunto que o grafo não prevê."""
    origem = _origem(arquivo, base)
    if origem.camada not in ("services", "dto"):
        return []
    return [
        f"{_onde(arquivo, base, importado)} "
        f"(dto de {destino.assunto} fora do grafo de {origem.assunto})"
        for importado, destino in _importacoes_de_app(arquivo)
        if destino.camada == "dto"
        and destino.assunto != origem.assunto
        and destino.assunto not in GRAFO[origem.assunto]
        and importado != USUARIO_AUTENTICADO
    ]


def _outro_assunto(arquivo: Path, base: Path = BASE) -> list[str]:
    """Controller, repository ou schema que importa um arquivo de outro assunto."""
    origem = _origem(arquivo, base)
    if origem.camada not in ("controllers", "repositories", "schemas"):
        return []
    return [
        f"{_onde(arquivo, base, importado)} "
        f"({origem.camada} só importa o próprio assunto, não o de {destino.assunto})"
        for importado, destino in _importacoes_de_app(arquivo)
        if destino.assunto not in (None, origem.assunto)
    ]


def _esconde(escondido: str, donos: list[str]) -> Regra:
    """Regra: só os arquivos de `donos` importam `escondido` (ocultação de informação)."""

    def regra(arquivo: Path, base: Path = BASE) -> list[str]:
        caminho = arquivo.relative_to(base).as_posix()
        if caminho in donos:
            return []
        verbo = "importa" if len(donos) == 1 else "importam"
        return [
            f"{_onde(arquivo, base, importado)} (só {' e '.join(donos)} {verbo} {escondido})"
            for importado in _importacoes(arquivo)
            if importado == escondido or importado.startswith(escondido + ".")
        ]

    return regra


_security_fora_do_lugar = _esconde(
    "app.core.security", ["app/services/usuario_service.py", "app/dependencies.py"]
)
_cedula_fora_do_lugar = _esconde("app.core.cedula", ["app/services/votacao_service.py"])


def _framework_nos_dados(arquivo: Path, base: Path = BASE) -> list[str]:
    """`dto/` e `models/enums.py` que importam fastapi, pydantic ou sqlalchemy."""
    origem = _origem(arquivo, base)
    if origem.camada not in ("dto", "enums"):
        return []
    return [
        f"{_onde(arquivo, base, importado)} ({origem.camada} sem framework: {biblioteca})"
        for importado in _importacoes(arquivo)
        if (biblioteca := importado.split(".")[0]) in FRAMEWORKS_DOS_DADOS
    ]


def _arquivo_do_modulo(importado: str, base: Path) -> Path | None:
    """O arquivo de onde vem o nome importado: `app.core.web.X` -> `base/app/core/web.py`."""
    partes = importado.split(".")
    for fim in range(len(partes), 1, -1):
        caminho = base.joinpath(*partes[:fim])
        if caminho.with_suffix(".py").is_file():
            return caminho.with_suffix(".py")
        if (caminho / "__init__.py").is_file():
            return caminho / "__init__.py"
    return None


def _framework_indireto(arquivo: Path, base: Path = BASE) -> list[str]:
    """Service ou repository que chega ao FastAPI por um módulo de `app/` que importa.

    Segue os imports de `app` em profundidade (cada módulo uma vez) e acusa o primeiro import
    direto de quem leva ao framework.
    """
    origem = _origem(arquivo, base)
    proibidas = SEM_FRAMEWORK_NEM_INDIRETO.get(origem.camada)
    if not proibidas:
        return []
    problemas = []
    visitados: set[Path] = set()
    for importado, _ in _importacoes_de_app(arquivo):
        pendentes = [_arquivo_do_modulo(importado, base)]
        while pendentes:
            atual = pendentes.pop()
            if atual is None or atual in visitados:
                continue
            visitados.add(atual)
            for nome in _importacoes(atual):
                biblioteca = nome.split(".")[0]
                if biblioteca in proibidas:
                    caminho = atual.relative_to(base).as_posix()
                    motivo = (
                        f"{origem.camada} não chega a {biblioteca} nem indiretamente: "
                        f"{caminho} importa {nome}"
                    )
                    problemas.append(f"{_onde(arquivo, base, importado)} ({motivo})")
                elif biblioteca == "app":
                    pendentes.append(_arquivo_do_modulo(nome, base))
    return problemas


def _import_relativo(arquivo: Path, base: Path = BASE) -> list[str]:
    """Imports relativos: neles o destino não fica claro, e a fronteira passaria sem conferência."""
    return [
        f"{_onde(arquivo, base, importado)} (import relativo: use `app.…`)"
        for importado in _importacoes(arquivo)
        if importado.startswith(".")
    ]


REGRAS: dict[str, Regra] = {
    "direcao": _direcao,
    "grafo": _fora_do_grafo,
    "repository_e_models": _repository_ou_model_de_outro_assunto,
    "dto": _dto_de_outro_assunto_fora_do_grafo,
    "assunto": _outro_assunto,
    "security": _security_fora_do_lugar,
    "cedula": _cedula_fora_do_lugar,
    "framework": _framework_nos_dados,
    "framework_indireto": _framework_indireto,
    "relativo": _import_relativo,
}


def _arquivos(pasta: str) -> list[Path]:
    """Os `.py` de uma pasta de `app/`, sem o `__init__.py` (raiz de composição)."""
    return sorted(p for p in (RAIZ / pasta).glob("*.py") if p.name != "__init__.py")


def _todos_os_arquivos() -> list[Path]:
    return sorted(RAIZ.rglob("*.py"))


def _violacoes(regra: Regra, arquivos: list[Path]) -> list[str]:
    return [problema for arquivo in arquivos for problema in regra(arquivo)]


# Direção das camadas: uma regra por linha da tabela ---------------------------------------------

# Uma regra por camada de `PODE_IMPORTAR`, sobre todos os arquivos dela:
# - controllers: só traduzem HTTP; recebem o service pronto e não tocam no banco;
# - services: não sabem nada de HTTP; falam em DTOs e não conhecem rota, JSON nem login;
# - repositories: só consultam o banco; não conhecem as camadas que os usam nem HTTP;
# - schemas: são o JSON da API; conhecem DTOs e enums, mas não as tabelas nem o banco;
# - dto: dado puro; só usa `models/enums.py` e outros DTOs;
# - models: só usam `core/database.py`, `core/validadores.py` e os enums;
# - core: a base de todas as camadas, não depende de nenhuma delas (os enums valem para todos,
#   e o `dto` só para `core/cedula.py`).
CAMADAS_COM_REGRA_DE_DIRECAO = [
    "controllers",
    "services",
    "repositories",
    "schemas",
    "dto",
    "models",
    "core",
]


@pytest.mark.parametrize("camada", CAMADAS_COM_REGRA_DE_DIRECAO)
def test_camada_respeita_a_tabela_de_dependencias(camada):
    """Nenhum arquivo da camada importa o que a tabela de dependências proíbe."""
    assert _violacoes(_direcao, _arquivos(camada)) == []


# Grafo entre os services ------------------------------------------------------------------------


def _arestas_reais() -> dict[str, set[str]]:
    """Quem importa quem de verdade, de assunto para assunto, olhando todas as camadas."""
    reais: dict[str, set[str]] = {assunto: set() for assunto in GRAFO}
    for pasta in ("controllers", "services", "repositories", "schemas", "dto", "models"):
        for arquivo in _arquivos(pasta):
            origem = _origem(arquivo)
            if origem.assunto is None:
                continue
            for _, destino in _importacoes_de_app(arquivo):
                if destino.assunto not in (None, origem.assunto):
                    reais[origem.assunto].add(destino.assunto)
    return reais


def _achar_ciclo(grafo: dict[str, set[str]]) -> list[str] | None:
    """O primeiro ciclo do grafo (`["a", "b", "a"]`), ou `None` se não houver."""
    visitados: set[str] = set()

    def visitar(no: str, caminho: list[str]) -> list[str] | None:
        if no in caminho:
            return [*caminho[caminho.index(no) :], no]
        if no in visitados:
            return None
        visitados.add(no)
        for vizinho in sorted(grafo.get(no, ())):
            ciclo = visitar(vizinho, [*caminho, no])
            if ciclo:
                return ciclo
        return None

    for no in sorted(grafo):
        ciclo = visitar(no, [])
        if ciclo:
            return ciclo
    return None


def test_services_so_dependem_do_grafo_e_sem_ciclo():
    """Um service só depende dos services do `GRAFO`; nem ele nem os imports reais fazem ciclo."""
    assert _violacoes(_fora_do_grafo, _arquivos("services")) == []
    assert _achar_ciclo(GRAFO) is None, "o GRAFO declarado tem ciclo"
    assert _achar_ciclo(_arestas_reais()) is None, "os imports reais formam um ciclo"


# Fronteira do assunto ---------------------------------------------------------------------------


def test_nada_atravessa_a_fronteira_do_assunto():
    """Para os dados de outro assunto, o service pede ao service dele, nunca ao repository.

    Services e DTOs só usam como tipo o DTO dos assuntos vizinhos no grafo (a exceção é o
    `UsuarioAutenticado`, que chega a todo service como parâmetro). Fora dos services, nada
    atravessa a fronteira do assunto.
    """
    services = _arquivos("services")
    fora_dos_services = _arquivos("controllers") + _arquivos("repositories") + _arquivos("schemas")

    violacoes = [
        *_violacoes(_repository_ou_model_de_outro_assunto, services),
        *_violacoes(_dto_de_outro_assunto_fora_do_grafo, services + _arquivos("dto")),
        *_violacoes(_outro_assunto, fora_dos_services),
    ]

    assert violacoes == []


# Ocultação de informação ------------------------------------------------------------------------


def test_security_e_cedula_ficam_escondidas():
    """Bcrypt e JWT só são usados pelo login e pela leitura do token; a cédula, só pela votação."""
    arquivos = _todos_os_arquivos()

    violacoes = [
        *_violacoes(_security_fora_do_lugar, arquivos),
        *_violacoes(_cedula_fora_do_lugar, arquivos),
    ]

    assert violacoes == []


# Sem framework e sem import relativo ------------------------------------------------------------


def test_dto_e_enums_nao_importam_framework():
    """DTO é dataclass simples, e os enums são usados por todas as camadas: nenhum conhece HTTP,
    JSON nem banco."""
    arquivos = [*_arquivos("dto"), RAIZ / "models" / "enums.py"]
    assert _violacoes(_framework_nos_dados, arquivos) == []


def test_services_e_repositories_nao_chegam_ao_fastapi_nem_indiretamente():
    """Nem pelos módulos de `core/` que importam: o que é do FastAPI fica em `core/web.py`."""
    arquivos = _arquivos("services") + _arquivos("repositories")
    assert _violacoes(_framework_indireto, arquivos) == []


def test_nenhum_import_relativo():
    """Todo import é absoluto (`from app...`), para o destino ficar claro e ser conferido."""
    assert _violacoes(_import_relativo, _todos_os_arquivos()) == []


# Sanidade ---------------------------------------------------------------------------------------


def test_toda_camada_tem_os_arquivos_esperados():
    """Sem os arquivos da camada, as regras dela passariam sem testar nada."""
    faltando = {}
    for pasta, esperados in ARQUIVOS_ESPERADOS.items():
        existentes = {a.stem.removesuffix(SUFIXOS[pasta]) for a in _arquivos(pasta)}
        if esperados - existentes:
            faltando[pasta] = sorted(esperados - existentes)
    assert faltando == {}


# Testes do próprio verificador ------------------------------------------------------------------


def _gravar(base: Path, caminho: str, texto: str) -> Path:
    arquivo = base / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def _codigo(importado: str) -> str:
    """`app.core.security.criar_token` -> `from app.core.security import criar_token`."""
    modulo, _, nome = importado.rpartition(".")
    return f"from {modulo} import {nome}\n"


SO_SECURITY = "só app/services/usuario_service.py e app/dependencies.py importam app.core.security"
SO_CEDULA = "só app/services/votacao_service.py importa app.core.cedula"
ELEITOR_REPO = "app.repositories.eleitor_repository.EleitorRepository"
ELEITOR_SERVICE = "app.services.eleitor_service.EleitorService"
ELEITOR_MODEL = "app.models.eleitor.Eleitor"

# Um exemplo de cada tipo de violação: (regra, arquivo, o que ele importa, motivo da acusação).
# A primeira parte cobre uma linha de cada camada da tabela; o resto, as demais regras.
VIOLACOES = [
    # direção das camadas
    (
        "direcao",
        "app/controllers/eleitor_controller.py",
        ELEITOR_REPO,
        "controllers não importa repositories",
    ),
    (
        "direcao",
        "app/controllers/eleitor_controller.py",
        ELEITOR_MODEL,
        "controllers não importa models",
    ),
    (
        "direcao",
        "app/controllers/eleitor_controller.py",
        "sqlalchemy.orm.Session",
        "controllers não importa sqlalchemy",
    ),
    (
        "direcao",
        "app/services/eleitor_service.py",
        "app.controllers.eleitor_controller.roteador",
        "services não importa controllers",
    ),
    (
        "direcao",
        "app/services/eleitor_service.py",
        "fastapi.HTTPException",
        "services não importa fastapi",
    ),
    ("direcao", "app/services/eleitor_service.py", "app.main.app", "services não importa raiz"),
    (
        "direcao",
        "app/repositories/eleitor_repository.py",
        ELEITOR_SERVICE,
        "repositories não importa services",
    ),
    ("direcao", "app/schemas/eleitor_schema.py", ELEITOR_MODEL, "schemas não importa models"),
    ("direcao", "app/dto/eleitor_dto.py", ELEITOR_SERVICE, "dto não importa services"),
    ("direcao", "app/models/eleitor.py", ELEITOR_SERVICE, "models não importa services"),
    (
        "direcao",
        "app/models/eleitor.py",
        "app.core.relogio.agora",
        "models não importa core.relogio",
    ),
    ("direcao", "app/core/relogio.py", ELEITOR_SERVICE, "core não importa services"),
    (
        "direcao",
        "app/core/security.py",
        "app.dto.usuario_dto.UsuarioAutenticado",
        "core não importa dto",
    ),
    # grafo entre os services
    (
        "grafo",
        "app/services/votacao_service.py",
        "app.services.candidato_service.CandidatoService",
        "aresta fora do grafo: votacao não depende de candidato",
    ),
    (
        "grafo",
        "app/services/usuario_service.py",
        ELEITOR_SERVICE,
        "aresta fora do grafo: usuario não depende de eleitor",
    ),
    # fronteira do assunto
    (
        "repository_e_models",
        "app/services/votacao_service.py",
        ELEITOR_REPO,
        "o service de votacao usa repositories de eleitor",
    ),
    (
        "repository_e_models",
        "app/services/votacao_service.py",
        ELEITOR_MODEL,
        "o service de votacao usa models de eleitor",
    ),
    (
        "dto",
        "app/services/votacao_service.py",
        "app.dto.candidato_dto.CandidatoResumo",
        "dto de candidato fora do grafo de votacao",
    ),
    (
        "assunto",
        "app/controllers/votacao_controller.py",
        "app.schemas.eleitor_schema.EleitorResposta",
        "controllers só importa o próprio assunto, não o de eleitor",
    ),
    # ocultação de informação
    (
        "security",
        "app/controllers/auth_controller.py",
        "app.core.security.criar_token",
        SO_SECURITY,
    ),
    ("cedula", "app/services/eleicao_service.py", "app.core.cedula.emitir_cedula", SO_CEDULA),
    # dto/ e enums sem framework
    ("framework", "app/dto/eleitor_dto.py", "pydantic.BaseModel", "dto sem framework: pydantic"),
    ("framework", "app/models/enums.py", "sqlalchemy.Enum", "enums sem framework: sqlalchemy"),
    # import relativo
    (
        "relativo",
        "app/services/eleitor_service.py",
        "..repositories.eleitor_repository",
        "import relativo: use `app.…`",
    ),
]


# Famílias de regras: o que cada arquivo importa (direção, frameworks e imports relativos), a
# fronteira entre os assuntos e a ocultação de informação.
FAMILIAS = {
    "direcao": {"direcao", "framework", "relativo"},
    "assunto": {"grafo", "repository_e_models", "dto", "assunto"},
    "ocultacao": {"security", "cedula"},
}


@pytest.mark.parametrize("familia", list(FAMILIAS))
def test_verificador_acusa_cada_tipo_de_violacao(tmp_path, familia):
    """Para cada tipo de violação da família, a regra certa acusa o import proibido e só ele."""
    exemplos = [v for v in VIOLACOES if v[0] in FAMILIAS[familia]]
    assert {regra for regra, *_ in exemplos} == FAMILIAS[familia]  # nenhuma regra sem exemplo

    for regra, caminho, importado, motivo in exemplos:
        arquivo = _gravar(tmp_path, caminho, _codigo(importado))

        assert REGRAS[regra](arquivo, tmp_path) == [f"{caminho} importa {importado} ({motivo})"]


# O que cada camada pode importar: nenhuma regra acusa estes arquivos.
PERMITIDOS = {
    "app/controllers/votacao_controller.py": [
        "fastapi.APIRouter",
        "app.core.relogio.obter_agora",
        "app.dependencies.VotacaoServiceDep",
        "app.dto.votacao_dto.PedidoRegistro",
        "app.models.enums.Perfil",
        "app.schemas.votacao_schema.CedulaResposta",
    ],
    "app/services/votacao_service.py": [
        "sqlalchemy.orm.Session",
        "app.core.cedula.emitir_cedula",
        "app.dto.eleicao_dto.EleicaoResumo",
        "app.dto.usuario_dto.UsuarioAutenticado",
        "app.dto.votacao_dto.Escolha",
        "app.models.enums.Cargo",
        "app.models.voto.Voto",
        "app.repositories.votacao_repository.VotacaoRepository",
        "app.services.eleicao_service.EleicaoService",
        "app.services.eleitor_service.EleitorService",
    ],
    "app/services/usuario_service.py": ["app.core.security", "app.models.usuario.Usuario"],
    "app/repositories/votacao_repository.py": [
        "sqlalchemy.select",
        "app.core.paginacao.Paginacao",
        "app.dto.votacao_dto.ContagemVoto",
        "app.models.voto.Voto",
    ],
    "app/schemas/votacao_schema.py": [
        "pydantic.BaseModel",
        "app.core.validadores.MAIOR_ID",
        "app.dto.votacao_dto.Participacao",
        "app.models.enums.Cargo",
    ],
    "app/dto/apuracao_dto.py": ["app.dto.votacao_dto.ContagemVoto", "app.models.enums.Cargo"],
    "app/models/voto.py": [
        "sqlalchemy.String",
        "app.core.database.Base",
        "app.core.validadores.so_digitos",
        "app.models.enums.CARGOS_VALIDOS",
    ],
    "app/models/enums.py": ["app.core.validadores.so_digitos"],
    "app/core/cedula.py": ["app.dto.votacao_dto.Escolha", "app.models.enums.Cargo"],
    "app/dependencies.py": ["fastapi.Depends", "app.core.security", "app.services.eleitor_service"],
    "app/main.py": ["app.controllers.auth_controller"],
}


def test_verificador_aceita_o_que_a_tabela_permite(tmp_path):
    """O verificador não acusa import permitido (senão toda regra falharia à toa)."""
    acusacoes = {}
    for caminho, importados in PERMITIDOS.items():
        arquivo = _gravar(tmp_path, caminho, "".join(_codigo(i) for i in importados))
        for nome, regra in REGRAS.items():
            if problemas := regra(arquivo, tmp_path):
                acusacoes[f"{nome}: {caminho}"] = problemas

    assert acusacoes == {}


def test_verificador_acha_o_framework_indireto(tmp_path):
    """O caminho até o FastAPI é acusado no import do service; sem o framework no caminho, não."""
    _gravar(tmp_path, "app/core/web.py", "from fastapi import Query\n")
    _gravar(tmp_path, "app/core/paginacao.py", "from app.core.web import obter_paginacao\n")
    _gravar(tmp_path, "app/core/relogio.py", "from datetime import datetime\n")
    service = _gravar(
        tmp_path,
        "app/services/eleitor_service.py",
        "from app.core.relogio import agora\nfrom app.core.paginacao import Paginacao\n",
    )
    controller = _gravar(
        tmp_path, "app/controllers/eleitor_controller.py", "from app.core.web import Query\n"
    )

    assert _framework_indireto(service, tmp_path) == [
        "app/services/eleitor_service.py importa app.core.paginacao.Paginacao (services não "
        "chega a fastapi nem indiretamente: app/core/web.py importa fastapi.Query)"
    ]
    assert _framework_indireto(controller, tmp_path) == []  # controller pode usar o FastAPI


def test_verificador_acha_o_ciclo():
    """`_achar_ciclo` devolve o caminho do ciclo, ou `None` quando não há."""
    assert _achar_ciclo({"usuario": {"eleitor"}, "eleitor": {"usuario"}}) == [
        "eleitor",
        "usuario",
        "eleitor",
    ]
    assert _achar_ciclo({"a": {"b"}, "b": {"c"}, "c": {"a"}}) == ["a", "b", "c", "a"]
    assert _achar_ciclo({"a": {"b", "c"}, "b": {"c"}, "c": set()}) is None


CLASSIFICACAO = [
    ("app.services.eleitor_service.EleitorService", Local("services", "eleitor", "eleitor")),
    ("app.controllers.auth_controller.roteador", Local("controllers", "auth", "usuario")),
    ("app.dto.candidatura_dto.NovaCandidaturaDados", Local("dto", "candidatura", "eleicao")),
    (
        "app.models.registro_votacao.RegistroVotacao",
        Local("models", "registro_votacao", "votacao"),
    ),
    ("app.models.enums.Cargo", Local("enums")),
    ("app.core.security.criar_token", Local("core", "security")),
    ("app.dependencies.obter_usuario_logado", Local("dependencies")),
    ("app.models", Local("raiz")),
    ("app.scripts.seed_demo", Local("raiz")),
    ("fastapi.APIRouter", None),
]

FORA_DO_MAPA = [
    "app.services.foo_service",  # assunto que não existe
    "app.services.eleitor",  # sem o sufixo da camada
    "app.models.foo",  # entidade que não existe
    "app.helpers.foo",  # pasta que não existe
    "app.services.EleitorService",  # nome importado do pacote, não do arquivo
]


def test_classificacao_de_cada_nome_importado():
    """Cada nome importado cai na camada e no assunto certos; o que está fora do mapa falha alto."""
    for nome, esperado in CLASSIFICACAO:
        assert _local(nome) == esperado, nome

    for nome in FORA_DO_MAPA:
        with pytest.raises(ValueError, match="sem classificação"):
            _local(nome)
