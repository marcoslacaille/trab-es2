"""Rotas de eleitores. Sem regra de negócio: recebem, chamam o serviço e devolvem o esquema."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao
from app.compartilhado.openapi import respostas_de_erro
from app.compartilhado.relogio import obter_agora
from app.eleitores import servico
from app.eleitores.dominio import NovoEleitorDados
from app.eleitores.esquemas import EleitorResposta, NovoEleitor

# `Perfil` e `UsuarioAutenticado` vêm de `dependencias`, a única parte de `identidade` (além do
# serviço) que as rotas de outros módulos podem importar (seção 5).
from app.identidade.dependencias import Perfil, exige_perfil

roteador = APIRouter(prefix="/eleitores", tags=["Eleitores"])

somente_chefe = [Depends(exige_perfil(Perfil.CHEFE_SECAO))]
IdDoEleitor = Annotated[int, Path(gt=0, description="Identificador do eleitor.")]


@roteador.post(
    "",
    status_code=201,
    response_model=EleitorResposta,
    dependencies=somente_chefe,
    summary="Cadastra um eleitor",
    description=(
        "Cria o eleitor e a credencial dele (perfil ELEITOR) de uma vez. O CPF pode vir com ou "
        "sem pontuação e é gravado só com dígitos. A senha nunca é devolvida (RN-20 a RN-22)."
    ),
    responses=respostas_de_erro(401, 403, 409, 422),
)
def cadastrar_eleitor(
    dados: NovoEleitor,
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleitorResposta:
    eleitor = servico.cadastrar_eleitor(sessao, NovoEleitorDados(**dados.model_dump()), agora)
    return EleitorResposta.model_validate(eleitor)
