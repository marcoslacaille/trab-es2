"""Regras puras de identidade: a regra de senha, sem banco."""

from app.core.exceptions import DadosInvalidos
from app.core.security import BYTES_MAXIMOS_SENHA

TAMANHO_MINIMO_SENHA = 8


def validar_senha(senha: str) -> None:
    """RN-05: de 8 caracteres até 72 bytes em UTF-8, e não pode ser só espaços.

    Levanta `DadosInvalidos` com o código `SENHA_INVALIDA` (422) se a senha não servir.
    """
    if senha.strip() == "":
        raise DadosInvalidos("A senha não pode conter apenas espaços.", codigo="SENHA_INVALIDA")
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise DadosInvalidos(
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.",
            codigo="SENHA_INVALIDA",
        )
    if len(senha.encode("utf-8")) > BYTES_MAXIMOS_SENHA:
        raise DadosInvalidos(
            f"A senha deve ter no máximo {BYTES_MAXIMOS_SENHA} bytes (UTF-8).",
            codigo="SENHA_INVALIDA",
        )
