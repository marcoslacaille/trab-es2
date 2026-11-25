"""Regras puras de eleições: ciclo de vida, validações da abertura e links HATEOAS.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from app.compartilhado.dominio import (
    CARGOS_DO_SEGUNDO_TURNO,
    DIGITOS_POR_CARGO,
    Cargo,
    numero_valido_para_cargo,
)
from app.core.exceptions import ConflitoDeEstado, DadosInvalidos

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
class CandidaturaDetalhada:
    """Uma candidatura com os dados de exibição do candidato e do partido (seção 9.5).

    `partido_id` não está na lista da seção 9.5, mas o contrato "Criar candidatura" devolve o
    `id` do partido (D-066).
    """

    id: int
    eleicao_id: int
    cargo: Cargo
    numero: str
    candidato_id: int
    nome_urna: str
    data_nascimento: date
    partido_id: int
    partido_sigla: str
    partido_numero: int


@dataclass(frozen=True)
class NovaCandidaturaDados:
    """Tudo o que o Chefe informa para criar uma candidatura (RN-40)."""

    candidato_id: int
    partido_id: int
    cargo: Cargo
    numero: str


@dataclass(frozen=True)
class AlteracoesCandidatura:
    """O que pode mudar numa candidatura: cargo, número e partido. `None` = não alterar."""

    cargo: Cargo | None = None
    numero: str | None = None
    partido_id: int | None = None


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


def _validar_segundo_turno_completo(candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-17: no 2º turno, cada cargo com candidatura tem exatamente 2 (409 se não)."""
    incompletos = [
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade != CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO
    ]
    if incompletos:
        raise ConflitoDeEstado(
            "No 2º turno, cada cargo disputado precisa ter exatamente 2 candidaturas.",
            codigo="SEGUNDO_TURNO_INCOMPLETO",
            detalhes={"cargos": sorted(incompletos)},
        )


def _validar_cargos_do_segundo_turno(candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-45: no 2º turno só há candidaturas de Governador e Presidente (409 se não)."""
    proibidos = sorted(
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade > 0 and cargo not in CARGOS_DO_SEGUNDO_TURNO
    )
    if proibidos:
        raise ConflitoDeEstado(
            "No 2º turno só há Governador e Presidente.",
            codigo="CARGO_NAO_PERMITIDO_NO_TURNO",
            detalhes={"cargos": proibidos},
        )


def validar_candidaturas_no_turno(turno: int, candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-45: as candidaturas já cadastradas cabem no turno? Usada ao editar a eleição.

    Sem isto, trocar o turno de 1 para 2 deixaria um 2º turno com Senador ou com 3 candidatos a
    Presidente. No 1º turno não há restrição. No 2º, confere nesta ordem: só Governador e
    Presidente (`CARGO_NAO_PERMITIDO_NO_TURNO`, 409) e no máximo 2 por cargo
    (`LIMITE_SEGUNDO_TURNO`, 409); `detalhes.cargos` lista os cargos com problema.
    """
    if turno != 2:
        return
    _validar_cargos_do_segundo_turno(candidaturas_por_cargo)
    excedentes = sorted(
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade > CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO
    )
    if excedentes:
        raise ConflitoDeEstado(
            f"No 2º turno cada cargo tem no máximo {CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO} "
            "candidaturas.",
            codigo="LIMITE_SEGUNDO_TURNO",
            detalhes={"cargos": excedentes},
        )


def validar_abertura(
    eleicao: EleicaoResumo,
    agora: datetime,
    existe_outra_aberta: bool,
    candidaturas_por_cargo: dict[Cargo, int],
) -> None:
    """RN-13, RN-15, RN-16, RN-17 e RN-45: confere se a eleição pode ser aberta agora.

    Confere nesta ordem, e a primeira falha é a devolvida (todas são 409): status AGENDADA
    (`TRANSICAO_INVALIDA`); nenhuma outra eleição aberta (`OUTRA_ELEICAO_ABERTA`); hoje é a data
    da eleição (`FORA_DA_DATA`); horário entre a abertura (inclusive) e o encerramento
    (exclusive) (`FORA_DA_JANELA`); ao menos uma candidatura (`SEM_CANDIDATURAS`); no 2º turno,
    só Governador e Presidente (`CARGO_NAO_PERMITIDO_NO_TURNO`, segunda barreira da RN-45) e
    exatamente 2 candidaturas em cada cargo disputado (`SEGUNDO_TURNO_INCOMPLETO`).
    `candidaturas_por_cargo` só traz os cargos que têm candidatura.
    """
    if eleicao.status != StatusEleicao.AGENDADA:
        raise ConflitoDeEstado(
            "Só uma eleição AGENDADA pode ser aberta.",
            codigo="TRANSICAO_INVALIDA",
            detalhes={"status": eleicao.status.value},
        )
    if existe_outra_aberta:
        raise ConflitoDeEstado("Já existe outra eleição aberta.", codigo="OUTRA_ELEICAO_ABERTA")
    if agora.date() != eleicao.data:
        raise ConflitoDeEstado(
            "A eleição só pode ser aberta no dia dela.",
            codigo="FORA_DA_DATA",
            detalhes={"data_da_eleicao": eleicao.data.isoformat()},
        )
    if not eleicao.horario_abertura <= agora.time() < eleicao.horario_encerramento:
        raise ConflitoDeEstado(
            "A eleição só pode ser aberta dentro da janela de votação.",
            codigo="FORA_DA_JANELA",
            detalhes={
                "horario_abertura": eleicao.horario_abertura.isoformat(),
                "horario_encerramento": eleicao.horario_encerramento.isoformat(),
            },
        )
    if sum(candidaturas_por_cargo.values()) == 0:
        raise ConflitoDeEstado(
            "A eleição precisa de pelo menos uma candidatura para ser aberta.",
            codigo="SEM_CANDIDATURAS",
        )
    if eleicao.turno == 2:
        _validar_cargos_do_segundo_turno(candidaturas_por_cargo)
        _validar_segundo_turno_completo(candidaturas_por_cargo)


def validar_candidatura(
    eleicao: EleicaoResumo, cargo: Cargo, numero: str, quantidade_no_cargo: int
) -> None:
    """RN-42 e RN-45: confere o número e, no 2º turno, o cargo e o limite de candidaturas.

    `quantidade_no_cargo` é quantas candidaturas o cargo já tem na eleição, sem contar a que
    está sendo editada. Confere nesta ordem: número com os dígitos do cargo e sem zero à
    esquerda (`NUMERO_INVALIDO_PARA_CARGO`, 422); no 2º turno, só Governador e Presidente
    (`CARGO_NAO_PERMITIDO_NO_TURNO`, 409) e no máximo 2 por cargo (`LIMITE_SEGUNDO_TURNO`, 409).
    """
    if not numero_valido_para_cargo(numero, cargo):
        raise DadosInvalidos(
            f"O número {numero!r} não tem os dígitos do cargo {cargo.value}.",
            codigo="NUMERO_INVALIDO_PARA_CARGO",
            detalhes={"cargo": cargo.value, "digitos": DIGITOS_POR_CARGO[cargo]},
        )
    if eleicao.turno != 2:
        return
    if cargo not in CARGOS_DO_SEGUNDO_TURNO:
        raise ConflitoDeEstado(
            "No 2º turno só há Governador e Presidente.",
            codigo="CARGO_NAO_PERMITIDO_NO_TURNO",
            detalhes={"cargo": cargo.value},
        )
    if quantidade_no_cargo >= CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO:
        raise ConflitoDeEstado(
            f"No 2º turno cada cargo tem no máximo {CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO} "
            "candidaturas.",
            codigo="LIMITE_SEGUNDO_TURNO",
            detalhes={"cargo": cargo.value},
        )


def validar_encerramento(status: StatusEleicao) -> None:
    """RN-13 e RN-18: só se encerra uma eleição ABERTA, a qualquer hora.

    Levanta `ConflitoDeEstado` com `TRANSICAO_INVALIDA` (409).
    """
    if status != StatusEleicao.ABERTA:
        raise ConflitoDeEstado(
            "Só uma eleição ABERTA pode ser encerrada.",
            codigo="TRANSICAO_INVALIDA",
            detalhes={"status": status.value},
        )


def links_da_eleicao(eleicao: EleicaoResumo, perfil: str) -> list[Link]:
    """RN-19 (HATEOAS): as ações que o perfil pode fazer na eleição, dado o status dela.

    `self` sempre aparece. O resto segue a tabela da seção 9.5 do PLANO: o Chefe edita, gerencia
    candidaturas e abre a AGENDADA, e encerra a ABERTA; Eleitor e Candidato veem a apuração
    parcial da ABERTA (o Eleitor também a cédula); todos veem o resultado da ENCERRADA.
    """
    base = f"{PREFIXO_DA_API}/eleicoes/{eleicao.id}"
    apuracao = f"{PREFIXO_DA_API}/apuracao/eleicoes/{eleicao.id}"
    links = [Link("self", "GET", base)]

    if eleicao.status == StatusEleicao.AGENDADA and perfil == CHEFE_SECAO:
        links += [
            Link("editar", "PATCH", base),
            Link("candidaturas", "GET", f"{base}/candidaturas"),
            Link("nova-candidatura", "POST", f"{base}/candidaturas"),
            Link("abrir", "POST", f"{base}/abertura"),
        ]
    if eleicao.status == StatusEleicao.ABERTA:
        if perfil == CHEFE_SECAO:
            links.append(Link("encerrar", "POST", f"{base}/encerramento"))
        if perfil == ELEITOR:
            cedula = f"{PREFIXO_DA_API}/votacao/eleicoes/{eleicao.id}/cedula"
            links.append(Link("cedula", "GET", cedula))
        if perfil in (CHEFE_SECAO, ELEITOR, CANDIDATO):
            links.append(Link("apuracao-parcial", "GET", f"{apuracao}/parcial"))
    if eleicao.status == StatusEleicao.ENCERRADA:
        links.append(Link("resultado", "GET", f"{apuracao}/resultado"))
    return links
