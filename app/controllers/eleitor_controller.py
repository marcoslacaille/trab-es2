"""Controller de eleitores: recebe o HTTP e chama o `EleitorService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import AfterValidator

from app.core.openapi import respostas_de_erro
from app.core.paginacao import Paginacao
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID, sem_caractere_nulo
from app.core.web import PaginaResposta, obter_paginacao
from app.dependencies import EleitorServiceDep, UsuarioAutenticado, exige_perfil
from app.dto.eleitor_dto import AlteracoesEleitor, NovoEleitorDados
from app.models.enums import Perfil
from app.schemas.eleitor_schema import AlteracaoEleitor, EleitorResposta, NovoEleitor

roteador = APIRouter(prefix="/eleitores", tags=["Eleitores"])

somente_chefe = [Depends(exige_perfil(Perfil.CHEFE_SECAO))]
IdDoEleitor = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador do eleitor.")]


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
    service: EleitorServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleitorResposta:
    eleitor = service.cadastrar_eleitor(NovoEleitorDados(**dados.model_dump()), agora)
    return EleitorResposta.model_validate(eleitor)


@roteador.get(
    "",
    response_model=PaginaResposta[EleitorResposta],
    dependencies=somente_chefe,
    summary="Lista os eleitores",
    description="Ordenados por nome, com filtro opcional por parte do nome e paginação (RN-20).",
    responses=respostas_de_erro(401, 403, 422),
)
def listar_eleitores(
    service: EleitorServiceDep,
    paginacao: Annotated[Paginacao, Depends(obter_paginacao)],
    nome: Annotated[
        str | None,
        Query(max_length=120, description="Parte do nome, sem diferenciar maiúsculas."),
        AfterValidator(sem_caractere_nulo),
    ] = None,
) -> PaginaResposta[EleitorResposta]:
    pagina = service.listar_eleitores(nome, paginacao)
    return PaginaResposta[EleitorResposta](
        itens=[EleitorResposta.model_validate(eleitor) for eleitor in pagina.itens],
        pagina=pagina.pagina,
        tamanho=pagina.tamanho,
        total=pagina.total,
    )


# `/eu` precisa vir antes de `/{eleitor_id}`: o FastAPI casa as rotas na ordem declarada.
@roteador.get(
    "/eu",
    response_model=EleitorResposta,
    summary="Consulta os próprios dados de eleitor",
    description="O eleitor logado vê os próprios dados (RN-25).",
    responses=respostas_de_erro(401, 403, 404),
)
def consultar_meus_dados_de_eleitor(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.ELEITOR))],
    service: EleitorServiceDep,
) -> EleitorResposta:
    return EleitorResposta.model_validate(service.obter_eleitor_logado(usuario.id))


@roteador.get(
    "/{eleitor_id}",
    response_model=EleitorResposta,
    dependencies=somente_chefe,
    summary="Consulta um eleitor",
    description="Só o Chefe da Seção consulta eleitores pelo id (RN-20).",
    responses=respostas_de_erro(401, 403, 404, 422),
)
def consultar_eleitor(eleitor_id: IdDoEleitor, service: EleitorServiceDep) -> EleitorResposta:
    return EleitorResposta.model_validate(service.obter_eleitor(eleitor_id))


@roteador.patch(
    "/{eleitor_id}",
    response_model=EleitorResposta,
    dependencies=somente_chefe,
    summary="Altera um eleitor",
    description=(
        "Só nome, data de nascimento e senha podem mudar. CPF e título não mudam: mandar "
        "qualquer outro campo dá 422 (RN-22 e RN-23)."
    ),
    responses=respostas_de_erro(401, 403, 404, 422),
)
def alterar_eleitor(
    eleitor_id: IdDoEleitor,
    alteracao: AlteracaoEleitor,
    service: EleitorServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> EleitorResposta:
    eleitor = service.atualizar_eleitor(
        eleitor_id, AlteracoesEleitor(**alteracao.model_dump()), agora
    )
    return EleitorResposta.model_validate(eleitor)


@roteador.delete(
    "/{eleitor_id}",
    status_code=204,
    response_class=Response,
    dependencies=somente_chefe,
    summary="Exclui um eleitor",
    description=(
        "Apaga o eleitor e a credencial dele. Quem já votou não pode ser excluído: "
        "responde 409 `EXCLUSAO_BLOQUEADA` (RN-24)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def excluir_eleitor(eleitor_id: IdDoEleitor, service: EleitorServiceDep) -> Response:
    service.excluir_eleitor(eleitor_id)
    return Response(status_code=204)
