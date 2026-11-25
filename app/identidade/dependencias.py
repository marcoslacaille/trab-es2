"""Dependências FastAPI de autenticação, usadas pelas rotas de todos os módulos."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import obter_sessao
from app.core.exceptions import AcessoNegado, NaoAutenticado
from app.dto.usuario_dto import UsuarioAutenticado
from app.identidade import service
from app.models.enums import Perfil

# auto_error=False: nós mesmos respondemos 401 no formato padrão de erro da API.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def obter_usuario_atual(
    token: Annotated[str | None, Depends(esquema_oauth2)],
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> UsuarioAutenticado:
    """Toda rota protegida depende desta função (RN-06).

    RN-02: o token prova quem você é, mas o usuário é recarregado do banco a cada requisição;
    quem foi excluído depois do login perde o acesso na hora.
    """
    if not token:
        raise NaoAutenticado("Autenticação necessária.", codigo="NAO_AUTENTICADO")
    usuario = service.obter_usuario(sessao, security.ler_token_acesso(token))
    if usuario is None:
        raise NaoAutenticado("Token inválido ou expirado.", codigo="TOKEN_INVALIDO")
    return usuario


def exige_perfil(*perfis_permitidos: Perfil):
    """Cria uma dependência que só deixa passar os perfis informados (RN-03).

    Uso numa rota: `Depends(exige_perfil(Perfil.CHEFE_SECAO))`. Quem tem outro perfil recebe
    403 `PERFIL_NAO_AUTORIZADO`; sem login, 401 (a mesma de `obter_usuario_atual`).
    """

    def verificar(
        usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
    ) -> UsuarioAutenticado:
        if usuario.perfil not in perfis_permitidos:
            raise AcessoNegado(
                "Seu perfil não tem permissão para esta operação.",
                codigo="PERFIL_NAO_AUTORIZADO",
                detalhes={"perfis_permitidos": [perfil.value for perfil in perfis_permitidos]},
            )
        return usuario

    return verificar
