"""O que é do FastAPI e serve a todos os controllers: formato de erro, tratadores e paginação.

Fica separado de `core/exceptions.py` e `core/paginacao.py` porque os services importam esses
dois, e um service não depende do FastAPI nem indiretamente (o teste de camadas confere).
"""

import logging
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as ErroHttpDoFramework

from app.core.exceptions import (
    CONFLITO_DE_DADOS,
    ERROS_POR_RESTRICAO,
    ErroDeNegocio,
    nome_da_restricao,
)
from app.core.paginacao import MAIOR_PAGINA, TAMANHO_MAXIMO, Paginacao

registro = logging.getLogger(__name__)


# Formato de erro --------------------------------------------------------------------------------


class CorpoDoErro(BaseModel):
    """Conteúdo do erro: o que o cliente da API lê para decidir o que fazer."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo": "ELEICAO_NAO_ABERTA",
                "mensagem": "A eleição não está aberta.",
                "detalhes": {"status": "AGENDADA"},
            }
        }
    )

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


# Erros que o próprio FastAPI levanta (rota inexistente, método não permitido): código e mensagem.
ERROS_DO_FRAMEWORK = {
    404: ("ROTA_NAO_ENCONTRADA", "Rota não encontrada."),
    405: ("METODO_NAO_PERMITIDO", "Método não permitido para esta rota."),
}

# Primeiro item do `loc` do Pydantic: de onde veio o campo. Não interessa a quem usa a API.
_ORIGENS_DO_CAMPO = {"body", "query", "path", "header", "cookie"}


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
    """Registra no app os 5 tratadores de erro."""

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

    @app.exception_handler(ErroHttpDoFramework)
    async def tratar_erro_http_do_framework(
        requisicao: Request, erro: ErroHttpDoFramework
    ) -> JSONResponse:
        # Cobre também a HTTPException do FastAPI (subclasse desta). O cabeçalho `Allow` do 405
        # e outros cabeçalhos que o framework mandou são mantidos.
        codigo, mensagem = ERROS_DO_FRAMEWORK.get(
            erro.status_code, ("ERRO_HTTP", "Erro na requisição.")
        )
        return _resposta_de_erro(erro.status_code, codigo, mensagem, cabecalhos=erro.headers)

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


# Paginação --------------------------------------------------------------------------------------


def obter_paginacao(
    pagina: Annotated[
        int, Query(ge=1, le=MAIOR_PAGINA, description="Número da página (começa em 1).")
    ] = 1,
    tamanho: Annotated[
        int, Query(ge=1, le=TAMANHO_MAXIMO, description="Itens por página (de 1 a 100).")
    ] = 20,
) -> Paginacao:
    """Dependência FastAPI com `pagina` (1 a `MAIOR_PAGINA`, padrão 1) e `tamanho` (1 a 100).

    O teto de `pagina` evita que o deslocamento passe do BIGINT do banco (seria 500).
    """
    return Paginacao(pagina=pagina, tamanho=tamanho)


class PaginaResposta[T](BaseModel):
    """Resposta de toda listagem: os itens da página e o total geral para o cliente paginar."""

    itens: list[T]
    pagina: int = Field(description="Página devolvida (começa em 1).")
    tamanho: int = Field(description="Itens por página pedidos.")
    total: int = Field(description="Total de itens do filtro, somando todas as páginas.")
