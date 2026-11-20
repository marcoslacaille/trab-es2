"""Dependências FastAPI de autenticação, usadas pelas rotas de todos os módulos."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao
from app.compartilhado.erros import NaoAutenticado
from app.identidade import servico, tokens
from app.identidade.dominio import UsuarioAutenticado

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
    usuario = servico.obter_usuario(sessao, tokens.ler_token_acesso(token))
    if usuario is None:
        raise NaoAutenticado("Token inválido ou expirado.", codigo="TOKEN_INVALIDO")
    return usuario
