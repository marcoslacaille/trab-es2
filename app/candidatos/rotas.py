"""Rotas de candidatos e partidos. Sem regra de negócio: recebem, chamam o serviço e devolvem."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.candidatos import servico
from app.candidatos.dominio import NovoPartidoDados
from app.candidatos.esquemas import NovoPartido, PartidoResposta
from app.compartilhado.banco import obter_sessao
from app.compartilhado.openapi import respostas_de_erro
from app.compartilhado.relogio import obter_agora

# `identidade.dependencias` é a única parte de `identidade` (além do serviço) que as rotas de
# outros módulos podem importar (seção 5).
from app.identidade.dependencias import Perfil, exige_perfil, obter_usuario_atual

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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> PartidoResposta:
    partido = servico.criar_partido(sessao, NovoPartidoDados(**dados.model_dump()), agora)
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
def listar_partidos(sessao: Annotated[Session, Depends(obter_sessao)]) -> list[PartidoResposta]:
    return [PartidoResposta.model_validate(partido) for partido in servico.listar_partidos(sessao)]
