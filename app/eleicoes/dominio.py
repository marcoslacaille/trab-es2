"""Regras puras de eleições: ciclo de vida, validações da abertura e links HATEOAS.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from app.compartilhado.erros import ConflitoDeEstado, DadosInvalidos

PREFIXO_DA_API = "/api/v1"
DESCRICAO_MAXIMA = 120
CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO = 2

# Perfis como texto: `eleicoes` não importa `identidade`. O `Perfil` é um `StrEnum`, então
# `links_da_eleicao` aceita um `Perfil` normalmente.
CHEFE_SECAO = "CHEFE_SECAO"
ELEITOR = "ELEITOR"
CANDIDATO = "CANDIDATO"


class StatusEleicao(StrEnum):
    """Ciclo de vida da eleição, sempre nesta ordem e sem volta (RN-13)."""

    AGENDADA = "AGENDADA"
    ABERTA = "ABERTA"
    ENCERRADA = "ENCERRADA"


@dataclass(frozen=True)
class EleicaoResumo:
    """A eleição como as rotas e os outros módulos a enxergam. Nunca é o objeto ORM."""

    id: int
    descricao: str
    data: date
    turno: int
    horario_abertura: time
    horario_encerramento: time
    status: StatusEleicao
    aberta_em: datetime | None
    encerrada_em: datetime | None
    criado_em: datetime


@dataclass(frozen=True)
class Link:
    """Uma ação possível sobre a eleição (HATEOAS): nome, método HTTP e caminho."""

    rel: str
    metodo: str
    href: str


@dataclass(frozen=True)
class NovaEleicaoDados:
    """Tudo o que o Chefe informa para agendar uma eleição (RN-11)."""

    descricao: str
    data: date
    turno: int
    horario_abertura: time
    horario_encerramento: time


@dataclass(frozen=True)
class AlteracoesEleicao:
    """O que pode mudar enquanto a eleição está AGENDADA (RN-14). `None` = não alterar."""

    descricao: str | None = None
    data: date | None = None
    turno: int | None = None
    horario_abertura: time | None = None
    horario_encerramento: time | None = None


def validar_agendamento(dados: NovaEleicaoDados, hoje: date) -> NovaEleicaoDados:
    """RN-11: confere os dados de uma eleição ao criá-la ou editá-la e os devolve normalizados.

    A descrição, sem os espaços das pontas, tem de 1 a 120 caracteres; o turno é 1 ou 2; o
    horário de abertura vem antes do de encerramento; a data não é anterior a `hoje`.
    Levanta `DadosInvalidos` com `DADOS_INVALIDOS`, `JANELA_INVALIDA` ou `DATA_NO_PASSADO` (422).
    """
    descricao = dados.descricao.strip()
    if not 1 <= len(descricao) <= DESCRICAO_MAXIMA:
        raise DadosInvalidos(
            f"A descrição deve ter de 1 a {DESCRICAO_MAXIMA} caracteres.", codigo="DADOS_INVALIDOS"
        )
    if dados.turno not in (1, 2):
        raise DadosInvalidos("O turno deve ser 1 ou 2.", codigo="DADOS_INVALIDOS")
    if dados.horario_abertura >= dados.horario_encerramento:
        raise DadosInvalidos(
            "O horário de abertura deve ser anterior ao de encerramento.",
            codigo="JANELA_INVALIDA",
        )
    if dados.data < hoje:
        raise DadosInvalidos(
            "A data da eleição não pode ser anterior a hoje.", codigo="DATA_NO_PASSADO"
        )
    return NovaEleicaoDados(
        descricao=descricao,
        data=dados.data,
        turno=dados.turno,
        horario_abertura=dados.horario_abertura,
        horario_encerramento=dados.horario_encerramento,
    )


def validar_edicao(status: StatusEleicao) -> None:
    """RN-14: descrição, data, turno e horários só mudam enquanto a eleição está AGENDADA.

    Também vale para criar, alterar e remover candidaturas (RN-40).
    Levanta `ConflitoDeEstado` com `ELEICAO_NAO_EDITAVEL` (409).
    """
    if status != StatusEleicao.AGENDADA:
        raise ConflitoDeEstado(
            "Só uma eleição AGENDADA pode ser alterada.",
            codigo="ELEICAO_NAO_EDITAVEL",
            detalhes={"status": status.value},
        )
