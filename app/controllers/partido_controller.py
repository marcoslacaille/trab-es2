"""Controller de partidos: recebe o HTTP e chama o `PartidoService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.openapi import respostas_de_erro
from app.core.relogio import obter_agora
from app.dependencies import PartidoServiceDep, exige_perfil, obter_usuario_atual
from app.dto.partido_dto import NovoPartidoDados
from app.models.enums import Perfil
from app.schemas.partido_schema import NovoPartido, PartidoResposta

roteador = APIRouter()

somente_chefe = [Depends(exige_perfil(Perfil.CHEFE_SECAO))]


@roteador.post(
    "/partidos",
    status_code=201,
    response_model=PartidoResposta,
    dependencies=somente_chefe,
    tags=["Partidos"],
    summary="Cadastra um partido",
    description=(
        "Só o Chefe da Seção cadastra partidos. A sigla é gravada em maiúsculas. Sigla, nome e "
        "número são únicos: repetir qualquer um responde 409 `PARTIDO_DUPLICADO` (RN-30, RN-32)."
    ),
    responses=respostas_de_erro(401, 403, 409, 422),
)
def cadastrar_partido(
    dados: NovoPartido,
    service: PartidoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> PartidoResposta:
    partido = service.criar_partido(NovoPartidoDados(**dados.model_dump()), agora)
    return PartidoResposta.model_validate(partido)


@roteador.get(
    "/partidos",
    response_model=list[PartidoResposta],
    dependencies=[Depends(obter_usuario_atual)],
    tags=["Partidos"],
    summary="Lista os partidos",
    description="Qualquer usuário logado lista os partidos, ordenados por número (RN-30).",
    responses=respostas_de_erro(401),
)
def listar_partidos(service: PartidoServiceDep) -> list[PartidoResposta]:
    return [PartidoResposta.model_validate(partido) for partido in service.listar_partidos()]
