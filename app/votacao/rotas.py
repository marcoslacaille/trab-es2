"""Rotas da votação. Sem regra de negócio: recebem, chamam o serviço e devolvem o esquema.

Todas exigem o perfil ELEITOR (RN-50): Chefe e Candidato recebem 403 `PERFIL_NAO_AUTORIZADO`.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao
from app.compartilhado.openapi import respostas_de_erro
from app.compartilhado.relogio import obter_agora
from app.compartilhado.validadores import MAIOR_ID
from app.identidade.dependencias import Perfil, UsuarioAutenticado, exige_perfil
from app.votacao import servico
from app.votacao.dominio import PedidoRegistro
from app.votacao.esquemas import (
    CedulaResposta,
    ComprovanteVotoResposta,
    ParticipacaoResposta,
    PedidoConfirmacaoVoto,
    PedidoRegistroVoto,
    PreviaVotoResposta,
)

roteador = APIRouter(prefix="/votacao/eleicoes/{eleicao_id}", tags=["Votação"])

UsuarioEleitor = Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.ELEITOR))]
IdDaEleicao = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador da eleição.")]
Sessao = Annotated[Session, Depends(obter_sessao)]
Agora = Annotated[datetime, Depends(obter_agora)]


@roteador.get(
    "/cedula",
    response_model=CedulaResposta,
    summary="Consulta a cédula",
    description=(
        "Lista os cargos disputados, na ordem da urna, com os candidatos e se o eleitor já votou "
        "em cada um. Só com a eleição aberta e dentro da janela (RN-50 a 53, RN-55, RN-61)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def obter_cedula(
    eleicao_id: IdDaEleicao, usuario: UsuarioEleitor, sessao: Sessao, agora: Agora
) -> CedulaResposta:
    return CedulaResposta.de_cedula(servico.obter_cedula(sessao, usuario, eleicao_id, agora))


@roteador.post(
    "/votos/registro",
    response_model=PreviaVotoResposta,
    summary="Registra o voto (etapa 1)",
    description=(
        "Devolve a prévia do voto e a cédula assinada. **Nada é gravado**: pode repetir para "
        "mudar de ideia. Número com candidatura vira voto NOMINAL, número sem candidatura vira "
        "NULO, modo BRANCO vira BRANCO. A cédula vale 5 minutos (RN-54 a 58)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def registrar_voto(
    eleicao_id: IdDaEleicao,
    dados: PedidoRegistroVoto,
    usuario: UsuarioEleitor,
    sessao: Sessao,
    agora: Agora,
) -> PreviaVotoResposta:
    pedido = PedidoRegistro(cargo=dados.cargo, modo=dados.modo, numero=dados.numero)
    return PreviaVotoResposta.de_previa(
        servico.registrar_voto(sessao, usuario, eleicao_id, pedido, agora)
    )


@roteador.post(
    "/votos/confirmacao",
    status_code=201,
    response_model=ComprovanteVotoResposta,
    summary="Confirma o voto (etapa 2)",
    description=(
        "Grava o voto de forma definitiva e sem identificação. A resposta não diz em quem o "
        "eleitor votou. Um voto por eleitor, por cargo, por eleição; não pode ser alterado "
        "(RN-54, RN-56, RN-57, RN-59, RN-60)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def confirmar_voto(
    eleicao_id: IdDaEleicao,
    dados: PedidoConfirmacaoVoto,
    usuario: UsuarioEleitor,
    sessao: Sessao,
    agora: Agora,
) -> ComprovanteVotoResposta:
    comprovante = servico.confirmar_voto(sessao, usuario, eleicao_id, dados.token_cedula, agora)
    return ComprovanteVotoResposta.de_comprovante(comprovante)


@roteador.get(
    "/participacao",
    response_model=ParticipacaoResposta,
    summary="Consulta em quais cargos já votou",
    description="Lista os cargos disputados e se o eleitor já votou, sem a escolha (RN-61).",
    responses=respostas_de_erro(401, 403, 404, 422),
)
def obter_participacao(
    eleicao_id: IdDaEleicao, usuario: UsuarioEleitor, sessao: Sessao
) -> ParticipacaoResposta:
    return ParticipacaoResposta.de_participacao(
        servico.obter_participacao(sessao, usuario, eleicao_id)
    )
