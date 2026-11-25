"""Controller de candidaturas: recebe o HTTP e chama o `EleicaoService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.core.openapi import respostas_de_erro
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID
from app.dependencies import EleicaoServiceDep, UsuarioAutenticado, exige_perfil
from app.dto.candidatura_dto import AlteracoesCandidatura, NovaCandidaturaDados
from app.models.enums import Cargo, Perfil
from app.schemas.candidatura_schema import (
    AlteracaoCandidatura,
    CandidaturaResposta,
    NovaCandidatura,
)

# Candidaturas: sob `/eleicoes/{id}/candidaturas` (pela raiz do agregado) e `/candidaturas/minhas`.
roteador_candidaturas = APIRouter(tags=["Candidaturas"])

UsuarioChefe = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CHEFE_SECAO))]
UsuarioCandidato = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CANDIDATO))]
IdDaEleicao = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador da eleição.")]
IdDaCandidatura = Annotated[
    int, Path(gt=0, le=MAIOR_ID, description="Identificador da candidatura.")
]

CAMINHO_DAS_CANDIDATURAS = "/eleicoes/{eleicao_id}/candidaturas"


@roteador_candidaturas.get(
    CAMINHO_DAS_CANDIDATURAS,
    response_model=list[CandidaturaResposta],
    summary="Lista as candidaturas da eleição",
    description=(
        "Ordenadas pelo cargo (ordem da urna) e depois pelo número. Filtro opcional por cargo "
        "(RN-40)."
    ),
    responses=respostas_de_erro(401, 403, 404, 422),
)
def listar_candidaturas(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    cargo: Annotated[Cargo | None, Query(description="Filtra pelo cargo.")] = None,
) -> list[CandidaturaResposta]:
    return [
        CandidaturaResposta.de_candidatura(candidatura)
        for candidatura in service.listar_candidaturas(eleicao_id, cargo)
    ]


@roteador_candidaturas.post(
    CAMINHO_DAS_CANDIDATURAS,
    status_code=201,
    response_model=CandidaturaResposta,
    summary="Cria uma candidatura",
    description=(
        "Só com a eleição AGENDADA. Candidato e partido precisam existir; o número tem os "
        "dígitos do cargo e é único no cargo; o candidato disputa uma vez por eleição; no 2º "
        "turno só Governador e Presidente, no máximo 2 cada (RN-40 a RN-46)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def criar_candidatura(
    eleicao_id: IdDaEleicao,
    dados: NovaCandidatura,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidaturaResposta:
    candidatura = service.criar_candidatura(
        eleicao_id, NovaCandidaturaDados(**dados.model_dump()), agora
    )
    return CandidaturaResposta.de_candidatura(candidatura)


@roteador_candidaturas.patch(
    CAMINHO_DAS_CANDIDATURAS + "/{candidatura_id}",
    response_model=CandidaturaResposta,
    summary="Altera uma candidatura",
    description=(
        "Muda só cargo, número e partido, e só com a eleição AGENDADA. Candidato e eleição não "
        "mudam (RN-40 a RN-45)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def alterar_candidatura(
    eleicao_id: IdDaEleicao,
    candidatura_id: IdDaCandidatura,
    alteracao: AlteracaoCandidatura,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
) -> CandidaturaResposta:
    candidatura = service.editar_candidatura(
        eleicao_id, candidatura_id, AlteracoesCandidatura(**alteracao.model_dump())
    )
    return CandidaturaResposta.de_candidatura(candidatura)


@roteador_candidaturas.delete(
    CAMINHO_DAS_CANDIDATURAS + "/{candidatura_id}",
    status_code=204,
    summary="Remove uma candidatura",
    description="Só com a eleição AGENDADA (RN-40).",
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def remover_candidatura(
    eleicao_id: IdDaEleicao,
    candidatura_id: IdDaCandidatura,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
) -> Response:
    service.remover_candidatura(eleicao_id, candidatura_id)
    return Response(status_code=204)


@roteador_candidaturas.get(
    "/candidaturas/minhas",
    response_model=list[CandidaturaResposta],
    summary="Lista as candidaturas do candidato logado",
    description="O Candidato vê as próprias candidaturas, em todas as eleições (RN-47).",
    responses=respostas_de_erro(401, 403),
)
def listar_minhas_candidaturas(
    usuario: UsuarioCandidato,
    service: EleicaoServiceDep,
) -> list[CandidaturaResposta]:
    return [
        CandidaturaResposta.de_candidatura(candidatura)
        for candidatura in service.candidaturas_do_usuario(usuario.id)
    ]
