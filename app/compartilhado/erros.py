"""Erros de negócio e formato único de resposta de erro de toda a API."""

import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

registro = logging.getLogger(__name__)


class ErroDeNegocio(Exception):
    """Erro esperado, causado por uma regra de negócio. Vira uma resposta HTTP padronizada.

    O código do erro vai como argumento (e não como uma classe por erro) para evitar classite.
    Uso: `raise ConflitoDeEstado("A eleição não está aberta.", codigo="ELEICAO_NAO_ABERTA")`.
    """

    status_http = 409

    def __init__(self, mensagem: str, codigo: str, detalhes: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.detalhes = detalhes or {}


class NaoAutenticado(ErroDeNegocio):
    """401: não sei quem você é."""

    status_http = 401


class AcessoNegado(ErroDeNegocio):
    """403: sei quem você é e você não pode fazer isto."""

    status_http = 403


class NaoEncontrado(ErroDeNegocio):
    """404: o recurso do caminho não existe."""

    status_http = 404


class ConflitoDeEstado(ErroDeNegocio):
    """409: o pedido é válido, mas conflita com o estado atual."""

    status_http = 409


class DadosInvalidos(ErroDeNegocio):
    """422: o pedido em si está errado."""

    status_http = 422


class CorpoDoErro(BaseModel):
    """Conteúdo do erro: o que o cliente da API lê para decidir o que fazer."""

    codigo: str = Field(description="Código estável do erro (catálogo da seção 10 do PLANO).")
    mensagem: str = Field(description="Explicação legível para uma pessoa.")
    detalhes: dict = Field(default_factory=dict, description="Dados extras; pode ser vazio.")


class ErroResposta(BaseModel):
    """Formato de erro de todas as rotas: `{"erro": {"codigo", "mensagem", "detalhes"}}`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "erro": {
                    "codigo": "ELEICAO_NAO_ABERTA",
                    "mensagem": "A eleição não está aberta.",
                    "detalhes": {"status": "AGENDADA"},
                }
            }
        }
    )

    erro: CorpoDoErro


@dataclass(frozen=True)
class TraducaoDeRestricao:
    """Como uma restrição violada no banco aparece para o cliente da API."""

    codigo: str
    status_http: int
    mensagem: str


_FK_BLOQUEIA_EXCLUSAO = TraducaoDeRestricao(
    "EXCLUSAO_BLOQUEADA", 409, "Não é possível excluir: há registros que dependem deste."
)
_PARTIDO_DUPLICADO = TraducaoDeRestricao(
    "PARTIDO_DUPLICADO", 409, "Já existe um partido com esta sigla, nome ou número."
)

# Tabela da seção 6 do PLANO: nome da restrição (convenção de nomes do banco.py) -> erro da API.
ERROS_POR_RESTRICAO: dict[str, TraducaoDeRestricao] = {
    "uq_usuarios_cpf": TraducaoDeRestricao(
        "CPF_JA_CADASTRADO", 409, "Já existe um usuário com este CPF."
    ),
    "uq_eleitores_titulo_eleitor": TraducaoDeRestricao(
        "TITULO_JA_CADASTRADO", 409, "Já existe um eleitor com este título de eleitor."
    ),
    "uq_partidos_sigla": _PARTIDO_DUPLICADO,
    "uq_partidos_numero": _PARTIDO_DUPLICADO,
    "uq_partidos_nome": _PARTIDO_DUPLICADO,
    "uq_eleicoes_data_turno": TraducaoDeRestricao(
        "ELEICAO_DUPLICADA", 409, "Já existe uma eleição nesta data e turno."
    ),
    "uq_eleicoes_uma_aberta": TraducaoDeRestricao(
        "OUTRA_ELEICAO_ABERTA", 409, "Já existe outra eleição aberta."
    ),
    "uq_candidaturas_eleicao_id_cargo_numero": TraducaoDeRestricao(
        "NUMERO_JA_UTILIZADO", 409, "Este número já é usado por outra candidatura neste cargo."
    ),
    "uq_candidaturas_eleicao_id_candidato_id": TraducaoDeRestricao(
        "CANDIDATURA_DUPLICADA", 409, "Este candidato já tem candidatura nesta eleição."
    ),
    "pk_registros_votacao": TraducaoDeRestricao(
        "VOTO_JA_REGISTRADO", 409, "O eleitor já votou neste cargo nesta eleição."
    ),
    "fk_registros_votacao_eleitor_id_eleitores": _FK_BLOQUEIA_EXCLUSAO,
    "fk_candidaturas_candidato_id_candidatos": _FK_BLOQUEIA_EXCLUSAO,
}

CONFLITO_DE_DADOS = TraducaoDeRestricao(
    "CONFLITO_DE_DADOS", 409, "Os dados enviados conflitam com os já gravados."
)

# Primeiro item do `loc` do Pydantic: de onde veio o campo. Não interessa a quem usa a API.
_ORIGENS_DO_CAMPO = {"body", "query", "path", "header", "cookie"}


def nome_da_restricao(erro: IntegrityError) -> str | None:
    """Devolve o nome da restrição que o PostgreSQL acusou, ou None se ele não informou."""
    diagnostico = getattr(erro.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)


def _resposta_de_erro(
    status_http: int,
    codigo: str,
    mensagem: str,
    detalhes: dict | None = None,
    cabecalhos: dict[str, str] | None = None,
) -> JSONResponse:
    """Monta a resposta HTTP no formato padrão de erro."""
    conteudo = CorpoDoErro(codigo=codigo, mensagem=mensagem, detalhes=detalhes or {})
    corpo = ErroResposta(erro=conteudo)
    return JSONResponse(
        status_code=status_http, content=corpo.model_dump(mode="json"), headers=cabecalhos
    )


def _nome_do_campo(localizacao: tuple) -> str:
    """Transforma o `loc` do Pydantic (ex.: ('body', 'cpf')) em 'cpf'."""
    partes = localizacao[1:] if localizacao and localizacao[0] in _ORIGENS_DO_CAMPO else localizacao
    return ".".join(str(parte) for parte in partes)


def registrar_tratadores(app: FastAPI) -> None:
    """Registra no app os 4 tratadores de erro (seção 5 do PLANO)."""

    @app.exception_handler(ErroDeNegocio)
    async def tratar_erro_de_negocio(requisicao: Request, erro: ErroDeNegocio) -> JSONResponse:
        # No 401, o cabeçalho diz ao cliente qual esquema de autenticação usar (RFC 6750).
        cabecalhos = {"WWW-Authenticate": "Bearer"} if erro.status_http == 401 else None
        return _resposta_de_erro(
            erro.status_http, erro.codigo, erro.mensagem, erro.detalhes, cabecalhos
        )

    @app.exception_handler(RequestValidationError)
    async def tratar_dados_invalidos(
        requisicao: Request, erro: RequestValidationError
    ) -> JSONResponse:
        campos = [
            {
                "campo": _nome_do_campo(problema["loc"]),
                # Validadores nossos levantam ValueError; o Pydantic põe esse prefixo na frente.
                "mensagem": problema["msg"].removeprefix("Value error, "),
            }
            for problema in erro.errors()
        ]
        return _resposta_de_erro(
            422, "DADOS_INVALIDOS", "Dados inválidos na requisição.", {"campos": campos}
        )

    @app.exception_handler(IntegrityError)
    async def tratar_erro_de_integridade(requisicao: Request, erro: IntegrityError) -> JSONResponse:
        nome = nome_da_restricao(erro)
        traducao = ERROS_POR_RESTRICAO.get(nome, CONFLITO_DE_DADOS) if nome else CONFLITO_DE_DADOS
        # Só o nome da restrição vai para o log: os valores gravados podem ser dados pessoais.
        registro.warning("Restrição do banco violada: %s", nome)
        return _resposta_de_erro(traducao.status_http, traducao.codigo, traducao.mensagem)

    @app.exception_handler(Exception)
    async def tratar_erro_inesperado(requisicao: Request, erro: Exception) -> JSONResponse:
        # O detalhe vai só para o log; a resposta não pode vazar nada do servidor.
        registro.error(
            "Erro inesperado em %s %s", requisicao.method, requisicao.url.path, exc_info=erro
        )
        return _resposta_de_erro(500, "ERRO_INTERNO", "Erro interno. Tente novamente mais tarde.")
