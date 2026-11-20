"""Núcleo compartilhado (shared kernel): o que todos os contextos precisam entender igual."""

from enum import StrEnum

from app.compartilhado.validadores import so_digitos


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


def numero_valido_para_cargo(numero: str, cargo: Cargo) -> bool:
    """Só dígitos (0 a 9, ASCII), sem zero à esquerda, na quantidade do cargo (RN-42)."""
    return so_digitos(numero) and numero[0] != "0" and len(numero) == DIGITOS_POR_CARGO[cargo]
