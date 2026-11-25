"""Controller da apuração: recebe o HTTP e chama o `ApuracaoService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import respostas_de_erro
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID
from app.dependencies import (
    ApuracaoServiceDep,
    UsuarioAutenticado,
    exige_perfil,
    obter_usuario_atual,
)
from app.models.enums import Cargo, Perfil
from app.schemas.apuracao_schema import ApuracaoResposta

roteador = APIRouter(prefix="/apuracao/eleicoes/{eleicao_id}", tags=["Apuração"])

IdDaEleicao = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador da eleição.")]
CargoPedido = Annotated[
    Cargo | None, Query(description="Limita a apuração a um cargo. Sem ele, todos os disputados.")
]
Agora = Annotated[datetime, Depends(obter_agora)]
UsuarioDaParcial = Annotated[
    UsuarioAutenticado,
    Depends(exige_perfil(Perfil.CHEFE_SECAO, Perfil.ELEITOR, Perfil.CANDIDATO)),
]
UsuarioLogado = Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)]


@roteador.get(
    "/parcial",
    response_model=ApuracaoResposta,
    summary="Acompanha a apuração parcial",
    description=(
        "Contagem atualizada a cada consulta, só com a eleição ABERTA. Eleitor e Chefe veem todos "
        "os cargos; o Candidato vê só o cargo da sua candidatura nesta eleição (RN-70 a 72, "
        "RN-74 a 79). Aqui `mais_votado` é quem lidera até agora."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def apuracao_parcial(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioDaParcial,
    service: ApuracaoServiceDep,
    agora: Agora,
    cargo: CargoPedido = None,
) -> ApuracaoResposta:
    return ApuracaoResposta.de_apuracao(service.apuracao_parcial(usuario, eleicao_id, cargo, agora))


@roteador.get(
    "/resultado",
    response_model=ApuracaoResposta,
    summary="Consulta o resultado final",
    description=(
        "Resultado da eleição ENCERRADA, visível a qualquer perfil autenticado: votos, "
        "percentuais, brancos, nulos, mais votado por cargo e comparecimento (RN-70, RN-73 a 79)."
    ),
    responses=respostas_de_erro(401, 404, 409, 422),
)
def resultado_final(
    eleicao_id: IdDaEleicao,
    usuario: UsuarioLogado,
    service: ApuracaoServiceDep,
    agora: Agora,
    cargo: CargoPedido = None,
) -> ApuracaoResposta:
    return ApuracaoResposta.de_apuracao(service.resultado_final(usuario, eleicao_id, cargo, agora))
