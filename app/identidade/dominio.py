"""Regras puras de identidade: perfis, usuário autenticado e regra de senha (sem banco)."""

from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import DadosInvalidos
from app.core.security import BYTES_MAXIMOS_SENHA
from app.models.enums import Perfil

TAMANHO_MINIMO_SENHA = 8


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Quem está logado, como os outros módulos e as rotas enxergam. Nunca traz a senha."""

    id: int
    nome: str
    cpf: str
    perfil: Perfil


@dataclass(frozen=True)
class ResultadoDoLogin:
    """O que um login bem-sucedido entrega: o token de acesso, quando expira e quem é o usuário."""

    access_token: str
    expira_em: datetime
    usuario: UsuarioAutenticado


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
