"""DTOs de usuário: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import Perfil


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
