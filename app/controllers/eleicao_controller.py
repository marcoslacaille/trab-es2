"""Controller de eleições: recebe o HTTP e chama o `EleicaoService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import respostas_de_erro
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID
from app.dependencies import (
    EleicaoServiceDep,
    UsuarioAutenticado,
    exige_perfil,
    obter_usuario_atual,
)
from app.dto.eleicao_dto import AlteracoesEleicao, NovaEleicaoDados
from app.models.enums import Perfil, StatusEleicao
from app.schemas.eleicao_schema import AlteracaoEleicao, EleicaoResposta, NovaEleicao

roteador = APIRouter(prefix="/eleicoes", tags=["Eleições"])

UsuarioChefe = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CHEFE_SECAO))]
UsuarioLogado = Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)]
IdDaEleicao = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador da eleição.")]


@roteador.post(
    "",
    status_code=201,
    response_model=EleicaoResposta,
    summary="Cria uma eleição",
    description=(
        "Agenda uma eleição (status AGENDADA). Turno 1 ou 2, abertura antes do encerramento e "
        "data não anterior a hoje. Não pode haver outra eleição na mesma data e turno "
        "(RN-10, RN-11, RN-12)."
    ),
    responses=respostas_de_erro(401, 403, 409, 422),
)
def criar_eleicao(
    dados: NovaEleicao,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    eleicao = service.criar_eleicao(NovaEleicaoDados(**dados.model_dump()), agora)
    return EleicaoResposta.de_eleicao(eleicao, usuario.perfil)


@roteador.get(
    "",
    response_model=list[EleicaoResposta],
    summary="Lista as eleições",
    description="Qualquer usuário logado lista as eleições, com filtro opcional de status (RN-19).",
    responses=respostas_de_erro(401, 422),
)
def listar_eleicoes(
    usuario: UsuarioLogado,
    service: EleicaoServiceDep,
    status: Annotated[StatusEleicao | None, Query(description="Filtra pela situação.")] = None,
) -> list[EleicaoResposta]:
    return [
        EleicaoResposta.de_eleicao(eleicao, usuario.perfil)
        for eleicao in service.listar_eleicoes(status)
    ]


@roteador.get(
    "/{eleicao_id}",
    response_model=EleicaoResposta,
    summary="Consulta uma eleição",
    description="Qualquer usuário logado consulta situação, horários e carimbos (RN-19).",
    responses=respostas_de_erro(401, 404, 422),
)
def consultar_eleicao(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioLogado,
    service: EleicaoServiceDep,
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(service.obter_eleicao(eleicao_id), usuario.perfil)


@roteador.patch(
    "/{eleicao_id}",
    response_model=EleicaoResposta,
    summary="Altera uma eleição",
    description=(
        "Só enquanto a eleição está AGENDADA. Os dados resultantes passam de novo pelas regras "
        "de agendamento (RN-10, RN-11, RN-12, RN-14)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def alterar_eleicao(
    eleicao_id: IdDaEleicao,
    alteracao: AlteracaoEleicao,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    alteracoes = AlteracoesEleicao(**alteracao.model_dump())
    eleicao = service.editar_eleicao(eleicao_id, alteracoes, agora)
    return EleicaoResposta.de_eleicao(eleicao, usuario.perfil)


@roteador.post(
    "/{eleicao_id}/abertura",
    response_model=EleicaoResposta,
    summary="Abre a votação",
    description=(
        "Muda a eleição de AGENDADA para ABERTA. Só no dia e dentro da janela, com pelo menos "
        "uma candidatura e nenhuma outra eleição aberta; no 2º turno, exatamente 2 candidaturas "
        "por cargo (RN-10, RN-13, RN-15 a RN-17)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def abrir_eleicao(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(service.abrir_eleicao(eleicao_id, agora), usuario.perfil)


@roteador.post(
    "/{eleicao_id}/encerramento",
    response_model=EleicaoResposta,
    summary="Encerra a votação",
    description=(
        "Muda a eleição de ABERTA para ENCERRADA, a qualquer hora (antes ou depois do horário "
        "previsto). Depois disso nenhum voto novo entra (RN-10, RN-13, RN-18)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def encerrar_eleicao(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioChefe,
    service: EleicaoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(service.encerrar_eleicao(eleicao_id, agora), usuario.perfil)
