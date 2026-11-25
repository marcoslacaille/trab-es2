"""Enums do domínio e as constantes de cargo, que todas as camadas entendem igual."""

from enum import StrEnum

from app.core.validadores import so_digitos


class Perfil(StrEnum):
    """Papel do usuário. Cada usuário tem exatamente um (RN-03)."""

    CHEFE_SECAO = "CHEFE_SECAO"
    ELEITOR = "ELEITOR"
    CANDIDATO = "CANDIDATO"


class Cargo(StrEnum):
    """Cargo disputado. A ordem é a da urna real e ordena a cédula e a apuração."""

    DEPUTADO_FEDERAL = "DEPUTADO_FEDERAL"
    DEPUTADO_ESTADUAL = "DEPUTADO_ESTADUAL"
    SENADOR = "SENADOR"
    GOVERNADOR = "GOVERNADOR"
    PRESIDENTE = "PRESIDENTE"


DIGITOS_POR_CARGO = {
    Cargo.DEPUTADO_FEDERAL: 4,
    Cargo.DEPUTADO_ESTADUAL: 5,
    Cargo.SENADOR: 3,
    Cargo.GOVERNADOR: 2,
    Cargo.PRESIDENTE: 2,
}

CARGOS_DO_SEGUNDO_TURNO = {Cargo.GOVERNADOR, Cargo.PRESIDENTE}

# Texto da restrição `cargo_valido` das duas tabelas da votação.
CARGOS_VALIDOS = (
    "cargo IN ('DEPUTADO_FEDERAL','DEPUTADO_ESTADUAL','SENADOR','GOVERNADOR','PRESIDENTE')"
)


def numero_valido_para_cargo(numero: str, cargo: Cargo) -> bool:
    """Só dígitos (0 a 9, ASCII), sem zero à esquerda, na quantidade do cargo (RN-42)."""
    return so_digitos(numero) and numero[0] != "0" and len(numero) == DIGITOS_POR_CARGO[cargo]


class StatusEleicao(StrEnum):
    """Ciclo de vida da eleição, sempre nesta ordem e sem volta (RN-13)."""

    AGENDADA = "AGENDADA"
    ABERTA = "ABERTA"
    ENCERRADA = "ENCERRADA"


class TipoVoto(StrEnum):
    """O que o voto vale na apuração."""

    NOMINAL = "NOMINAL"
    BRANCO = "BRANCO"
    NULO = "NULO"


class ModoEscolha(StrEnum):
    """Como o eleitor escolhe: digitando um número ou apertando BRANCO (sem flag booleana)."""

    NUMERO = "NUMERO"
    BRANCO = "BRANCO"


class SituacaoCargo(StrEnum):
    """Como o cargo terminou (ou está) na apuração."""

    DEFINIDO = "DEFINIDO"
    EMPATE = "EMPATE"
    SEM_VOTOS_VALIDOS = "SEM_VOTOS_VALIDOS"
