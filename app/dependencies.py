"""Entrega os services, o usuário logado e o perfil exigido às rotas, por `Depends`."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import obter_sessao
from app.core.exceptions import AcessoNegado, NaoAutenticado
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.enums import Perfil
from app.services.apuracao_service import ApuracaoService
from app.services.candidato_service import CandidatoService
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService
from app.services.partido_service import PartidoService
from app.services.usuario_service import UsuarioService
from app.services.votacao_service import VotacaoService

# auto_error=False: nós mesmos respondemos 401 no formato padrão de erro da API.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

Sessao = Annotated[Session, Depends(obter_sessao)]


def obter_usuario_service(sessao: Sessao) -> UsuarioService:
    return UsuarioService(sessao)


UsuarioServiceDep = Annotated[UsuarioService, Depends(obter_usuario_service)]


def obter_eleitor_service(sessao: Sessao) -> EleitorService:
    return EleitorService(sessao)


EleitorServiceDep = Annotated[EleitorService, Depends(obter_eleitor_service)]


def obter_candidato_service(sessao: Sessao) -> CandidatoService:
    return CandidatoService(sessao)


CandidatoServiceDep = Annotated[CandidatoService, Depends(obter_candidato_service)]


def obter_partido_service(sessao: Sessao) -> PartidoService:
    return PartidoService(sessao)


PartidoServiceDep = Annotated[PartidoService, Depends(obter_partido_service)]


def obter_eleicao_service(sessao: Sessao) -> EleicaoService:
    return EleicaoService(sessao)


EleicaoServiceDep = Annotated[EleicaoService, Depends(obter_eleicao_service)]


def obter_votacao_service(sessao: Sessao) -> VotacaoService:
    return VotacaoService(sessao)


VotacaoServiceDep = Annotated[VotacaoService, Depends(obter_votacao_service)]


def obter_apuracao_service(sessao: Sessao) -> ApuracaoService:
    return ApuracaoService(sessao)


ApuracaoServiceDep = Annotated[ApuracaoService, Depends(obter_apuracao_service)]


def obter_usuario_atual(
    token: Annotated[str | None, Depends(esquema_oauth2)],
    service: UsuarioServiceDep,
) -> UsuarioAutenticado:
    """Toda rota protegida depende desta função (RN-06).

    RN-02: o token prova quem você é, mas o usuário é recarregado do banco a cada requisição;
    quem foi excluído depois do login perde o acesso na hora.
    """
    if not token:
        raise NaoAutenticado("Autenticação necessária.", codigo="NAO_AUTENTICADO")
    usuario = service.obter_usuario(security.ler_token_acesso(token))
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
