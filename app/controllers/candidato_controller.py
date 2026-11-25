"""Controller de candidatos: recebe o HTTP e chama o `CandidatoService`."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import AfterValidator

from app.core.openapi import respostas_de_erro
from app.core.paginacao import Paginacao
from app.core.relogio import obter_agora
from app.core.validadores import MAIOR_ID, sem_caractere_nulo
from app.core.web import PaginaResposta, obter_paginacao
from app.dependencies import CandidatoServiceDep, UsuarioAutenticado, exige_perfil
from app.dto.candidato_dto import AlteracoesCandidato, NovoCandidatoDados
from app.models.enums import Perfil
from app.schemas.candidato_schema import AlteracaoCandidato, CandidatoResposta, NovoCandidato

roteador = APIRouter()

somente_chefe = [Depends(exige_perfil(Perfil.CHEFE_SECAO))]
IdDoCandidato = Annotated[int, Path(gt=0, le=MAIOR_ID, description="Identificador do candidato.")]


@roteador.post(
    "/candidatos",
    status_code=201,
    response_model=CandidatoResposta,
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Cadastra um candidato",
    description=(
        "Cria o candidato e a credencial dele (perfil CANDIDATO) de uma vez. O CPF pode vir com "
        "ou sem pontuação e é gravado só com dígitos. A senha nunca é devolvida (RN-30, RN-31). "
        "Ligar o candidato a uma eleição é outra etapa: a candidatura."
    ),
    responses=respostas_de_erro(401, 403, 409, 422),
)
def cadastrar_candidato(
    dados: NovoCandidato,
    service: CandidatoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidatoResposta:
    candidato = service.cadastrar_candidato(NovoCandidatoDados(**dados.model_dump()), agora)
    return CandidatoResposta.model_validate(candidato)


@roteador.get(
    "/candidatos",
    response_model=PaginaResposta[CandidatoResposta],
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Lista os candidatos",
    description="Ordenados por nome, com filtro opcional por parte do nome e paginação (RN-30).",
    responses=respostas_de_erro(401, 403, 422),
)
def listar_candidatos(
    service: CandidatoServiceDep,
    paginacao: Annotated[Paginacao, Depends(obter_paginacao)],
    nome: Annotated[
        str | None,
        Query(max_length=120, description="Parte do nome, sem diferenciar maiúsculas."),
        AfterValidator(sem_caractere_nulo),
    ] = None,
) -> PaginaResposta[CandidatoResposta]:
    pagina = service.listar_candidatos(nome, paginacao)
    return PaginaResposta[CandidatoResposta](
        itens=[CandidatoResposta.model_validate(candidato) for candidato in pagina.itens],
        pagina=pagina.pagina,
        tamanho=pagina.tamanho,
        total=pagina.total,
    )


# `/eu` precisa vir antes de `/{candidato_id}`: o FastAPI casa as rotas na ordem declarada.
@roteador.get(
    "/candidatos/eu",
    response_model=CandidatoResposta,
    tags=["Candidatos"],
    summary="Consulta os próprios dados de candidato",
    description="O candidato logado vê os próprios dados (RN-30).",
    responses=respostas_de_erro(401, 403, 404),
)
def consultar_meus_dados_de_candidato(
    usuario: Annotated[UsuarioAutenticado, Depends(exige_perfil(Perfil.CANDIDATO))],
    service: CandidatoServiceDep,
) -> CandidatoResposta:
    return CandidatoResposta.model_validate(service.obter_candidato_logado(usuario.id))


@roteador.get(
    "/candidatos/{candidato_id}",
    response_model=CandidatoResposta,
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Consulta um candidato",
    description="Só o Chefe da Seção consulta candidatos pelo id (RN-30).",
    responses=respostas_de_erro(401, 403, 404, 422),
)
def consultar_candidato(
    candidato_id: IdDoCandidato, service: CandidatoServiceDep
) -> CandidatoResposta:
    return CandidatoResposta.model_validate(service.obter_candidato(candidato_id))


@roteador.patch(
    "/candidatos/{candidato_id}",
    response_model=CandidatoResposta,
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Altera um candidato",
    description=(
        "Só nome, nome de urna, data de nascimento e senha podem mudar. O CPF não muda: mandar "
        "qualquer outro campo dá 422 (RN-31 e RN-33)."
    ),
    responses=respostas_de_erro(401, 403, 404, 422),
)
def alterar_candidato(
    candidato_id: IdDoCandidato,
    alteracao: AlteracaoCandidato,
    service: CandidatoServiceDep,
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidatoResposta:
    candidato = service.atualizar_candidato(
        candidato_id, AlteracoesCandidato(**alteracao.model_dump()), agora
    )
    return CandidatoResposta.model_validate(candidato)


@roteador.delete(
    "/candidatos/{candidato_id}",
    status_code=204,
    response_class=Response,
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Exclui um candidato",
    description=(
        "Apaga o candidato e a credencial dele. Quem tem candidaturas não pode ser excluído: "
        "responde 409 `EXCLUSAO_BLOQUEADA`; remova as candidaturas antes (RN-33)."
    ),
    responses=respostas_de_erro(401, 403, 404, 409, 422),
)
def excluir_candidato(candidato_id: IdDoCandidato, service: CandidatoServiceDep) -> Response:
    service.excluir_candidato(candidato_id)
    return Response(status_code=204)
