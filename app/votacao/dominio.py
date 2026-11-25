"""Regras puras da votação: quando se pode votar, quem é apto e o que o eleitor escolheu.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP.
"""

from datetime import datetime

from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.votacao_dto import Escolha
from app.models.enums import (
    DIGITOS_POR_CARGO,
    Cargo,
    ModoEscolha,
    StatusEleicao,
    TipoVoto,
    numero_valido_para_cargo,
)


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
