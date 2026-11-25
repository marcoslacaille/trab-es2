"""Regras puras de eleitores: validações de idade e de título, sem banco."""

from datetime import date

from app.core.exceptions import DadosInvalidos
from app.core.validadores import calcular_idade, so_digitos

IDADE_MINIMA_ELEITOR = 16
DIGITOS_DO_TITULO = 12


def validar_idade_eleitor(data_nascimento: date, hoje: date) -> None:
    """RN-22: o eleitor precisa ter nascido no passado e ter 16 anos completos em `hoje`.

    Levanta `DadosInvalidos` com o código `IDADE_MINIMA` (422) nos dois casos.
    """
    if data_nascimento >= hoje:
        raise DadosInvalidos("A data de nascimento deve estar no passado.", codigo="IDADE_MINIMA")
    if calcular_idade(data_nascimento, hoje) < IDADE_MINIMA_ELEITOR:
        raise DadosInvalidos(
            f"O eleitor deve ter pelo menos {IDADE_MINIMA_ELEITOR} anos.", codigo="IDADE_MINIMA"
        )


def validar_titulo_eleitor(titulo_eleitor: str) -> None:
    """RN-21: o título tem exatamente 12 dígitos (0 a 9).

    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se não tiver.
    """
    if len(titulo_eleitor) != DIGITOS_DO_TITULO or not so_digitos(titulo_eleitor):
        raise DadosInvalidos(
            f"O título de eleitor deve ter {DIGITOS_DO_TITULO} dígitos.",
            codigo="DADOS_INVALIDOS",
        )
