"""Regras puras da votação: quando se pode votar, quem é apto e o que o eleitor escolheu.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.compartilhado.dominio import DIGITOS_POR_CARGO, Cargo, numero_valido_para_cargo
from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.eleicoes.dominio import CandidaturaDetalhada, EleicaoResumo, StatusEleicao


class TipoVoto(StrEnum):
    """O que o voto vale na apuração."""

    NOMINAL = "NOMINAL"
    BRANCO = "BRANCO"
    NULO = "NULO"


class ModoEscolha(StrEnum):
    """Como o eleitor escolhe: digitando um número ou apertando BRANCO (sem flag booleana)."""

    NUMERO = "NUMERO"
    BRANCO = "BRANCO"


@dataclass(frozen=True)
class Escolha:
    """O resultado de `resolver_escolha`: o tipo do voto e, se nominal, o candidato escolhido.

    Só o voto NOMINAL tem candidatura. Os dados de exibição (número, nome de urna e sigla do
    partido) servem à prévia que o eleitor vê antes de confirmar; nos outros tipos ficam nulos.
    """

    tipo: TipoVoto
    candidatura_id: int | None = None
    numero: str | None = None
    nome_urna: str | None = None
    partido_sigla: str | None = None


@dataclass(frozen=True)
class ContagemVoto:
    """Quantos votos há de um tipo, para uma candidatura (ou nenhuma), em um cargo."""

    cargo: Cargo
    tipo: TipoVoto
    candidatura_id: int | None
    total: int


@dataclass(frozen=True)
class Comparecimento:
    """Quantos eleitores votaram em ao menos um cargo, e quantos votaram em cada cargo."""

    eleitores_que_votaram: int
    por_cargo: dict[Cargo, int]


def validar_pode_votar(eleicao: EleicaoResumo, agora: datetime) -> None:
    """RN-51 e RN-52: a eleição precisa estar ABERTA e dentro da janela de horário.

    Levanta 409 `ELEICAO_NAO_ABERTA` se o status não for ABERTA. Levanta 409 `JANELA_ENCERRADA`
    se hoje não é o dia da eleição ou o horário de encerramento já passou (o Chefe ainda não
    encerrou, mas o voto é recusado).
    """
    if eleicao.status != StatusEleicao.ABERTA:
        raise ConflitoDeEstado(
            "A eleição não está aberta.",
            codigo="ELEICAO_NAO_ABERTA",
            detalhes={"status": eleicao.status.value},
        )
    if agora.date() != eleicao.data or agora.time() >= eleicao.horario_encerramento:
        raise ConflitoDeEstado(
            "A janela de votação desta eleição já terminou.",
            codigo="JANELA_ENCERRADA",
            detalhes={"horario_encerramento": eleicao.horario_encerramento.isoformat()},
        )


def validar_eleitor_apto(eleitor_criado_em: datetime, eleicao_aberta_em: datetime) -> None:
    """RN-53: só vota quem foi cadastrado até o instante da abertura da eleição.

    Cadastrado no mesmo instante da abertura ainda é apto. Depois disso, 403 `ELEITOR_NAO_APTO`.
    """
    if eleitor_criado_em > eleicao_aberta_em:
        raise AcessoNegado(
            "Você foi cadastrado depois da abertura desta eleição e não pode votar nela.",
            codigo="ELEITOR_NAO_APTO",
        )


def resolver_escolha(
    cargo: Cargo,
    modo: ModoEscolha,
    numero: str | None,
    candidaturas_do_cargo: list[CandidaturaDetalhada],
) -> Escolha:
    """RN-58: transforma o que o eleitor digitou no tipo de voto que vale.

    - Modo BRANCO vira voto BRANCO (o número é ignorado).
    - Modo NUMERO exige a quantidade de dígitos do cargo; se faltar número ou ele for inválido,
      422 `NUMERO_INVALIDO_PARA_CARGO`.
    - Número que pertence a uma candidatura vira voto NOMINAL; número sem candidatura vira NULO.

    `candidaturas_do_cargo` são as candidaturas da eleição neste cargo.
    """
    if modo == ModoEscolha.BRANCO:
        return Escolha(TipoVoto.BRANCO)

    if numero is None or not numero_valido_para_cargo(numero, cargo):
        raise DadosInvalidos(
            f"O número deve ter {DIGITOS_POR_CARGO[cargo]} dígitos para {cargo.value}.",
            codigo="NUMERO_INVALIDO_PARA_CARGO",
            detalhes={"cargo": cargo.value, "digitos": DIGITOS_POR_CARGO[cargo]},
        )
    for candidatura in candidaturas_do_cargo:
        if candidatura.numero == numero:
            return Escolha(
                TipoVoto.NOMINAL,
                candidatura_id=candidatura.id,
                numero=candidatura.numero,
                nome_urna=candidatura.nome_urna,
                partido_sigla=candidatura.partido_sigla,
            )
    return Escolha(TipoVoto.NULO)


@dataclass(frozen=True)
class PedidoRegistro:
    """O que o eleitor pede ao registrar o voto: o cargo e como escolhe (número ou BRANCO)."""

    cargo: Cargo
    modo: ModoEscolha
    numero: str | None = None


@dataclass(frozen=True)
class CandidatoDaCedula:
    """Como o candidato aparece para o eleitor na cédula e na prévia."""

    numero: str
    nome_urna: str
    partido_sigla: str


@dataclass(frozen=True)
class CargoDaCedula:
    """Um cargo disputado na cédula: dígitos do número, se o eleitor já votou e os candidatos."""

    cargo: Cargo
    digitos: int
    ja_votou: bool
    candidatos: list[CandidatoDaCedula]


@dataclass(frozen=True)
class CedulaDoEleitor:
    """A cédula da eleição: só os cargos disputados, na ordem da urna (RN-55)."""

    eleicao_id: int
    cargos: list[CargoDaCedula]


@dataclass(frozen=True)
class PreviaVoto:
    """O que o eleitor vê antes de confirmar. Nada foi gravado (RN-56)."""

    eleicao_id: int
    cargo: Cargo
    tipo: TipoVoto
    candidato: CandidatoDaCedula | None
    mensagem: str
    token_cedula: str
    expira_em: datetime


@dataclass(frozen=True)
class ComprovanteVoto:
    """A confirmação do voto. Não contém a escolha (RN-60)."""

    eleicao_id: int
    cargo: Cargo
    mensagem: str


@dataclass(frozen=True)
class CargoParticipacao:
    """Se o eleitor já votou em um cargo disputado. Nunca diz em quem (RN-61)."""

    cargo: Cargo
    ja_votou: bool


@dataclass(frozen=True)
class Participacao:
    """Em quais cargos da eleição o eleitor já votou (RN-61)."""

    eleicao_id: int
    cargos: list[CargoParticipacao]
