"""TA-01 / RN-03: fronteiras entre módulos (seção 5 do PLANO), verificadas com `ast`.

Cada arquivo de `app/` e cada nome importado é classificado como (módulo, camada). A
classificação entende os dois layouts que convivem durante a refatoração: o antigo, por módulo
(`app/<modulo>/<camada>.py`), e o novo, por camada (`app/<camada>/<assunto>_<camada>.py`).
As regras olham só a classificação, nunca o nome do arquivo.
"""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2] / "app"
BASE = RAIZ.parent
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
# O terceiro nome é o mesmo `UsuarioAutenticado` no layout novo (`Perfil` vira `models.enums`).
TIPOS_DE_IDENTIDADE = {
    "app.identidade.dominio.Perfil",
    "app.identidade.dominio.UsuarioAutenticado",
    "app.dto.usuario_dto.UsuarioAutenticado",
}

# Classificação (mapa da transição) --------------------------------------------------------------

COMPARTILHADO = "compartilhado"  # livre para todos os módulos
RAIZ_DE_COMPOSICAO = "raiz"  # main, dependencies, scripts, models/__init__: não é verificada

# Layout novo: pasta da camada -> (sufixo do arquivo, camada que as regras entendem).
PASTAS_DE_CAMADA = {
    "controllers": ("_controller", "controller"),
    "services": ("_service", "service"),
    "repositories": ("_repository", "repository"),
    "schemas": ("_schema", "schemas"),
    "dto": ("_dto", "dominio"),
}

# Assunto (o `<assunto>` do nome do arquivo) -> módulo.
ASSUNTOS = {
    "usuario": "identidade",
    "auth": "identidade",
    "eleitor": "eleitores",
    "candidato": "candidatos",
    "partido": "candidatos",
    "eleicao": "eleicoes",
    "candidatura": "eleicoes",
    "votacao": "votacao",
    "apuracao": "apuracao",
}

# Entidade (`app/models/<entidade>.py`) -> módulo.
ENTIDADES = {
    "usuario": "identidade",
    "eleitor": "eleitores",
    "candidato": "candidatos",
    "partido": "candidatos",
    "eleicao": "eleicoes",
    "candidatura": "eleicoes",
    "registro_votacao": "votacao",
    "voto": "votacao",
}

# Arquivos de `core/` que pertencem a um módulo; os outros são compartilhados.
CORE_DE_UM_MODULO = {
    "security": ("identidade", "tokens"),
    "cedula": ("votacao", "cedulas"),
}

# Primeiro nome depois de `app.` que é raiz de composição (inclui o `app/__init__.py`).
NOMES_DA_RAIZ = {"__init__", "main", "scripts"}

Classe = tuple[str | None, str | None]


def _classificar(alvo: str | Path) -> Classe:
    """Devolve (módulo, camada) de um arquivo de `app/` ou de um nome importado.

    - `Path` relativo a `BASE` (um arquivo): `app/dependencies.py` é raiz de composição.
    - `str` (um nome importado, como `app.services.eleitor_service.EleitorService`):
      `app.dependencies` é (identidade, dependencias).
    - Módulo e camada saem `("compartilhado", None)` ou `("raiz", None)` quando o destino não
      pertence a um módulo, e `(None, None)` para o que não é de `app` (stdlib, fastapi...).
    - O que está em `app/` mas fora do mapa levanta `ValueError`: melhor falhar do que deixar um
      arquivo sem verificação.
    """
    como_arquivo = isinstance(alvo, Path)
    if como_arquivo:
        alvo = alvo.with_suffix("").as_posix().replace("/", ".")
    partes = alvo.split(".")
    if partes[0] != "app" or len(partes) < 2:
        return None, None
    pasta, nome = partes[1], (partes[2] if len(partes) > 2 else None)

    if pasta in MODULOS:  # layout antigo: app/<modulo>/<arquivo>.py
        return pasta, nome
    if pasta == COMPARTILHADO:
        return COMPARTILHADO, None
    if pasta == "core":
        return CORE_DE_UM_MODULO.get(nome, (COMPARTILHADO, None))
    if pasta == "dependencies":
        return (RAIZ_DE_COMPOSICAO, None) if como_arquivo else ("identidade", "dependencias")

    pacote_de_camada = pasta == "models" or pasta in PASTAS_DE_CAMADA
    if pasta in NOMES_DA_RAIZ or (pacote_de_camada and nome in (None, "__init__")):
        return RAIZ_DE_COMPOSICAO, None
    if pasta == "models" and nome == "enums":
        return COMPARTILHADO, None
    if pasta == "models" and nome in ENTIDADES:
        return ENTIDADES[nome], "model"
    if pasta in PASTAS_DE_CAMADA and nome:
        sufixo, camada = PASTAS_DE_CAMADA[pasta]
        assunto = nome.removesuffix(sufixo)
        if assunto != nome and assunto in ASSUNTOS:
            return ASSUNTOS[assunto], camada
    raise ValueError(f"sem classificação no mapa da transição: {alvo}")


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


def _arquivos_dos_modulos() -> list[tuple[str, str, Path]]:
    """(módulo, camada, arquivo) de cada `.py` de `app/` que pertence a um dos módulos."""
    achados = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        modulo, camada = _classificar(arquivo.relative_to(BASE))
        if modulo in MODULOS:
            achados.append((modulo, camada, arquivo))
    return achados


def _arquivos(modulo: str, camada: str) -> list[Path]:
    """Todos os arquivos do par (módulo, camada), nos dois layouts."""
    return [a for m, c, a in _arquivos_dos_modulos() if (m, c) == (modulo, camada)]


def _onde(arquivo: Path, importado: str) -> str:
    return f"{arquivo.relative_to(BASE).as_posix()} importa {importado}"


def _tipo_de_identidade(importado: str, camada_do_arquivo: str | None) -> bool:
    return importado in TIPOS_DE_IDENTIDADE and camada_do_arquivo in ("dominio", "service")


def _violacoes_no_arquivo(arquivo: Path, base: Path = BASE) -> list[str]:
    """As importações de um arquivo de módulo (em `base/app/...`) que quebram as fronteiras."""
    modulo, camada_do_arquivo = _classificar(arquivo.relative_to(base))
    problemas = []
    for importado in _importacoes(arquivo):
        onde = f"{arquivo.relative_to(base).as_posix()} importa {importado}"
        if importado.startswith("."):
            problemas.append(onde + " (import relativo: use `app.<modulo>`)")
            continue
        outro, camada = _classificar(importado)
        if outro in (None, modulo, COMPARTILHADO):
            continue
        if _tipo_de_identidade(importado, camada_do_arquivo):
            continue  # D-103
        if outro not in MODULOS or outro not in ARESTAS[modulo] | {"identidade"}:
            problemas.append(onde + " (aresta fora do grafo)")
        elif outro == "identidade" and camada == "dependencias":
            if camada_do_arquivo != "controller":
                problemas.append(onde + " (dependencias só nas rotas)")
        elif outro not in ARESTAS[modulo]:
            problemas.append(onde + " (aresta fora do grafo)")
        elif camada == "service":
            continue
        elif camada == "dominio" and camada_do_arquivo in ("dominio", "service"):
            continue  # D-077 / D-098
        else:
            problemas.append(onde + " (só `service` de outro módulo)")
    return problemas


def _violacoes_de_fronteira() -> list[str]:
    return [
        problema
        for _, _, arquivo in _arquivos_dos_modulos()
        for problema in _violacoes_no_arquivo(arquivo)
    ]


def test_ta01_modulos_so_importam_o_que_o_grafo_permite():
    """TA-01 / RN-03: só `service` (e `dominio` como tipo, D-077) dos módulos vizinhos."""
    assert _violacoes_de_fronteira() == []


def test_ta01_nao_ha_ciclos_entre_modulos():
    """TA-01: o grafo de dependências reais não tem ciclo."""
    reais = {m: set() for m in MODULOS}
    for modulo, _, arquivo in _arquivos_dos_modulos():
        for importado in _importacoes(arquivo):
            outro, _ = _classificar(importado)
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
    for arquivo in _arquivos(modulo, "dominio"):
        for importado in _importacoes(arquivo):
            assert importado.split(".")[0] not in ("fastapi", "sqlalchemy"), _onde(
                arquivo, importado
            )


def _arquivo_de_enums() -> Path:
    """`models/enums.py`: os enums e as constantes de cargo, que todas as camadas usam."""
    return RAIZ / "models" / "enums.py"


def test_enums_nao_importam_fastapi_nem_sqlalchemy():
    """Os enums e as constantes compartilhadas também ficam livres de framework e banco."""
    arquivo = _arquivo_de_enums()
    for importado in _importacoes(arquivo):
        assert importado.split(".")[0] not in ("fastapi", "sqlalchemy"), _onde(arquivo, importado)


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_service_nao_importa_controller_nem_fastapi(modulo):
    """TA-01: `service.py` não importa `controller` nem FastAPI (seção 5, tabela de camadas)."""
    for arquivo in _arquivos(modulo, "service"):
        for importado in _importacoes(arquivo):
            assert importado.split(".")[0] != "fastapi", _onde(arquivo, importado)
            assert _classificar(importado) != (modulo, "controller"), _onde(arquivo, importado)


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_controller_nao_importa_repository_nem_model(modulo):
    """TA-01: `controller.py` não importa `repository` nem `model` (nem de outro módulo)."""
    for arquivo in _arquivos(modulo, "controller"):
        for importado in _importacoes(arquivo):
            _, camada = _classificar(importado)
            assert camada not in ("repository", "model"), _onde(arquivo, importado)


def _gravar(base: Path, caminho: str, texto: str) -> Path:
    arquivo = base / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def test_ta01_detecta_violacao_de_fronteira(tmp_path):
    """TA-01: o verificador de fato acusa cada importação proibida (teste do teste, D-148)."""
    # Layout antigo (por módulo).
    antigo = _gravar(
        tmp_path,
        "app/votacao/service.py",
        "from app.eleitores.repository import buscar\n"  # camada errada do vizinho
        "from app.candidatos.service import listar\n"  # aresta que o grafo não tem
        "from ..eleicoes import repository\n"  # import relativo
        "from app.identidade.dominio import validar_senha\n"  # função, não tipo
        "from app.eleicoes.service import obter_eleicao\n"  # permitido
        "from app.identidade.dominio import UsuarioAutenticado\n"  # permitido (D-103)
        "import app.votacao.model\n",  # o próprio módulo: permitido
    )

    assert _violacoes_no_arquivo(antigo, tmp_path) == [
        "app/votacao/service.py importa app.eleitores.repository.buscar"
        " (só `service` de outro módulo)",
        "app/votacao/service.py importa app.candidatos.service.listar (aresta fora do grafo)",
        "app/votacao/service.py importa ..eleicoes.repository"
        " (import relativo: use `app.<modulo>`)",
        "app/votacao/service.py importa app.identidade.dominio.validar_senha"
        " (aresta fora do grafo)",
    ]

    # Layout novo (por camada): um service que pega o repository de outro assunto.
    servico = _gravar(
        tmp_path,
        "app/services/votacao_service.py",
        "from app.repositories.eleitor_repository import EleitorRepository\n"  # repository alheio
        "from app.dependencies import obter_usuario_logado\n"  # dependencias fora de uma rota
        "from app.services.eleicao_service import EleicaoService\n"  # permitido
        "from app.dto.usuario_dto import UsuarioAutenticado\n"  # permitido (tipo de identidade)
        "from app.models.enums import Cargo\n"  # compartilhado: permitido
        "from app.models.voto import Voto\n"  # o próprio módulo: permitido
        "from app.repositories.votacao_repository import VotacaoRepository\n",  # idem
    )

    assert _violacoes_no_arquivo(servico, tmp_path) == [
        "app/services/votacao_service.py importa"
        " app.repositories.eleitor_repository.EleitorRepository (só `service` de outro módulo)",
        "app/services/votacao_service.py importa app.dependencies.obter_usuario_logado"
        " (dependencias só nas rotas)",
    ]

    # Layout novo: um controller que pega o model de outro módulo.
    controller = _gravar(
        tmp_path,
        "app/controllers/votacao_controller.py",
        "from app.models.eleitor import Eleitor\n"  # model alheio
        "from app.dependencies import obter_usuario_logado\n"  # permitido (rota)
        "from app.services.votacao_service import VotacaoService\n",  # o próprio módulo
    )

    assert _violacoes_no_arquivo(controller, tmp_path) == [
        "app/controllers/votacao_controller.py importa app.models.eleitor.Eleitor"
        " (só `service` de outro módulo)",
    ]


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_dominio_nao_importa_repository_nem_model(modulo):
    """TA-01 / D-148: `dominio.py` só tem regras puras; não lê o banco nem do próprio módulo."""
    for arquivo in _arquivos(modulo, "dominio"):
        for importado in _importacoes(arquivo):
            _, camada = _classificar(importado)
            assert camada not in ("repository", "model"), _onde(arquivo, importado)


@pytest.mark.parametrize("modulo", MODULOS)
def test_ta01_schemas_nao_importam_sqlalchemy(modulo):
    """TA-01 / D-148: `schemas.py` é o contrato HTTP; não conhece o banco."""
    for arquivo in _arquivos(modulo, "schemas"):
        for importado in _importacoes(arquivo):
            assert importado.split(".")[0] != "sqlalchemy", _onde(arquivo, importado)


# Testes do próprio verificador ------------------------------------------------------------------

# Todo módulo tem estas camadas; só a `apuracao` não guarda dados (sem repository nem model).
PARES_ESPERADOS = [
    (modulo, camada)
    for modulo in MODULOS
    for camada in ("controller", "service", "schemas", "dominio", "repository", "model")
    if modulo != "apuracao" or camada not in ("repository", "model")
]


def test_sanidade_toda_camada_esperada_tem_arquivos_para_verificar():
    """Sem arquivo num par (módulo, camada), as regras passariam sem testar nada."""
    existentes = {(modulo, camada) for modulo, camada, _ in _arquivos_dos_modulos()}
    assert [par for par in PARES_ESPERADOS if par not in existentes] == []


@pytest.mark.parametrize(
    ("alvo", "modulo", "camada"),
    [
        # layout antigo: arquivos
        ("app/eleitores/service.py", "eleitores", "service"),
        ("app/identidade/dependencias.py", "identidade", "dependencias"),
        ("app/identidade/senhas.py", "identidade", "senhas"),
        ("app/votacao/cedulas.py", "votacao", "cedulas"),
        ("app/apuracao/dominio.py", "apuracao", "dominio"),
        ("app/identidade/controller.py", "identidade", "controller"),
        # layout antigo: nomes importados
        ("app.eleicoes.repository.buscar", "eleicoes", "repository"),
        ("app.identidade.dominio.Perfil", "identidade", "dominio"),
        # layout novo: arquivos
        ("app/controllers/auth_controller.py", "identidade", "controller"),
        ("app/controllers/candidatura_controller.py", "eleicoes", "controller"),
        ("app/services/eleitor_service.py", "eleitores", "service"),
        ("app/repositories/partido_repository.py", "candidatos", "repository"),
        ("app/schemas/apuracao_schema.py", "apuracao", "schemas"),
        ("app/dto/votacao_dto.py", "votacao", "dominio"),
        ("app/models/partido.py", "candidatos", "model"),
        ("app/models/registro_votacao.py", "votacao", "model"),
        ("app/models/enums.py", "compartilhado", None),
        ("app/models/__init__.py", "raiz", None),
        ("app/core/security.py", "identidade", "tokens"),
        ("app/core/cedula.py", "votacao", "cedulas"),
        ("app/core/relogio.py", "compartilhado", None),
        ("app/dependencies.py", "raiz", None),
        ("app/main.py", "raiz", None),
        ("app/scripts/seed_demo.py", "raiz", None),
        # layout novo: nomes importados
        ("app.services.eleitor_service.EleitorService", "eleitores", "service"),
        ("app.models.eleitor.Eleitor", "eleitores", "model"),
        ("app.models.enums.Cargo", "compartilhado", None),
        ("app.core.security.criar_token", "identidade", "tokens"),
        ("app.dependencies", "identidade", "dependencias"),
        ("app.dependencies.obter_usuario_logado", "identidade", "dependencias"),
        ("app.models", "raiz", None),
        ("app.main", "raiz", None),
        # o que não é de `app`
        ("fastapi.APIRouter", None, None),
        ("sqlalchemy.orm", None, None),
    ],
)
def test_classificacao_nos_dois_layouts(alvo, modulo, camada):
    """Cada arquivo e cada nome importado cai no (módulo, camada) do mapa da transição."""
    esperado = (modulo, camada)
    if alvo.endswith(".py"):
        assert _classificar(Path(alvo)) == esperado
    else:
        assert _classificar(alvo) == esperado


@pytest.mark.parametrize(
    "alvo",
    [
        Path("app/services/foo_service.py"),  # assunto que não existe
        Path("app/services/eleitor.py"),  # sem o sufixo da camada
        Path("app/models/foo.py"),  # entidade que não existe
        Path("app/helpers/foo.py"),  # pasta que não existe
        "app.services.EleitorService",  # nome importado do pacote, não do arquivo
    ],
)
def test_classificacao_recusa_o_que_nao_esta_no_mapa(alvo):
    """Um arquivo fora do mapa precisa falhar alto, em vez de ficar sem verificação."""
    with pytest.raises(ValueError, match="sem classificação"):
        _classificar(alvo)
