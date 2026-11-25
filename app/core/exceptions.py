"""Erros de negócio e a tradução das restrições do banco em erros da API.

Não depende de framework web: os services levantam estes erros sem conhecer HTTP. O formato da
resposta de erro e os tratadores que o FastAPI chama ficam em `core/web.py`.
"""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError


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

# Tabela de tradução: nome da restrição (convenção de nomes de core/database.py) -> erro da API.
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


def nome_da_restricao(erro: IntegrityError) -> str | None:
    """Devolve o nome da restrição que o PostgreSQL acusou, ou None se ele não informou."""
    diagnostico = getattr(erro.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)
