"""Rotas de autenticação: login e consulta do usuário logado. Sem regra de negócio."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao
from app.compartilhado.openapi import respostas_de_erro
from app.identidade import servico
from app.identidade.dependencias import obter_usuario_atual
from app.identidade.dominio import UsuarioAutenticado
from app.identidade.esquemas import LoginResposta, UsuarioLogadoResposta, UsuarioResposta

roteador = APIRouter(prefix="/auth", tags=["Autenticação"])


@roteador.post(
    "/login",
    response_model=LoginResposta,
    summary="Entra no sistema com CPF e senha",
    description=(
        "Recebe um formulário OAuth2 (`application/x-www-form-urlencoded`): `username` é o CPF "
        "(com ou sem pontuação) e `password` é a senha. Devolve o token JWT de acesso, que vale "
        "60 minutos. CPF inexistente e senha errada dão a mesma resposta 401 (RN-01)."
    ),
    responses=respostas_de_erro(401, 422),
)
def login(
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> LoginResposta:
    resultado = servico.autenticar(sessao, formulario.username, formulario.password)
    return LoginResposta(
        access_token=resultado.access_token,
        expira_em=resultado.expira_em,
        usuario=UsuarioResposta.model_validate(resultado.usuario),
    )


@roteador.get(
    "/me",
    response_model=UsuarioLogadoResposta,
    summary="Consulta o usuário logado",
    description=(
        "Devolve os dados do dono do token, lidos do banco no momento da requisição (RN-02). "
        "Se o usuário foi excluído depois do login, o token deixa de valer."
    ),
    responses=respostas_de_erro(401),
)
def consultar_usuario_logado(
    usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
) -> UsuarioLogadoResposta:
    return UsuarioLogadoResposta.model_validate(usuario)
