"""Controller de eleições e candidaturas: recebe o HTTP, chama o `service` e devolve o JSON."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.core.database import obter_sessao
from app.core.openapi import respostas_de_erro
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID
from app.eleicoes import service
from app.eleicoes.dominio import (
    AlteracoesCandidatura,
    AlteracoesEleicao,
    NovaCandidaturaDados,
    NovaEleicaoDados,
)
from app.eleicoes.schemas import (
    AlteracaoCandidatura,
    AlteracaoEleicao,
    CandidaturaResposta,
    EleicaoResposta,
    NovaCandidatura,
    NovaEleicao,
)

# `identidade.dependencias` é a única parte de `identidade` (além do serviço) que as rotas de
# outros módulos podem importar (seção 5).
from app.identidade.dependencias import UsuarioAutenticado, exige_perfil, obter_usuario_atual
from app.models.enums import Cargo, Perfil, StatusEleicao

roteador = APIRouter(prefix="/eleicoes", tags=["Eleições"])
# Candidaturas: sob `/eleicoes/{id}/candidaturas` (pela raiz do agregado) e `/candidaturas/minhas`.
roteador_candidaturas = APIRouter(tags=["Candidaturas"])

UsuarioChefe = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CHEFE_SECAO))]
UsuarioLogado = Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)]
UsuarioCandidato = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CANDIDATO))]
IdDaEleicao = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador da eleição.")]
IdDaCandidatura = Annotated[
    int, Path(gt=0, le=MAIOR_ID, description="Identificador da candidatura.")
]


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    eleicao = service.criar_eleicao(sessao, NovaEleicaoDados(**dados.model_dump()), agora)
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
    sessao: Annotated[Session, Depends(obter_sessao)],
    status: Annotated[StatusEleicao | None, Query(description="Filtra pela situação.")] = None,
) -> list[EleicaoResposta]:
    return [
        EleicaoResposta.de_eleicao(eleicao, usuario.perfil)
        for eleicao in service.listar_eleicoes(sessao, status)
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
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(service.obter_eleicao(sessao, eleicao_id), usuario.perfil)


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    alteracoes = AlteracoesEleicao(**alteracao.model_dump())
    eleicao = service.editar_eleicao(sessao, eleicao_id, alteracoes, agora)
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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(
        service.abrir_eleicao(sessao, eleicao_id, agora), usuario.perfil
    )


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleicaoResposta:
    return EleicaoResposta.de_eleicao(
        service.encerrar_eleicao(sessao, eleicao_id, agora), usuario.perfil
    )


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    cargo: Annotated[Cargo | None, Query(description="Filtra pelo cargo.")] = None,
) -> list[CandidaturaResposta]:
    return [
        CandidaturaResposta.de_candidatura(candidatura)
        for candidatura in service.listar_candidaturas(sessao, eleicao_id, cargo)
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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidaturaResposta:
    candidatura = service.criar_candidatura(
        sessao, eleicao_id, NovaCandidaturaDados(**dados.model_dump()), agora
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
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> CandidaturaResposta:
    candidatura = service.editar_candidatura(
        sessao, eleicao_id, candidatura_id, AlteracoesCandidatura(**alteracao.model_dump())
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
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> Response:
    service.remover_candidatura(sessao, eleicao_id, candidatura_id)
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
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> list[CandidaturaResposta]:
    return [
        CandidaturaResposta.de_candidatura(candidatura)
        for candidatura in service.candidaturas_do_usuario(sessao, usuario.id)
    ]
