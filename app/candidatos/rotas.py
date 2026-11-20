"""Rotas de candidatos e partidos. Sem regra de negócio: recebem, chamam o serviço e devolvem."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.candidatos import servico
from app.candidatos.dominio import AlteracoesCandidato, NovoCandidatoDados, NovoPartidoDados
from app.candidatos.esquemas import (
    AlteracaoCandidato,
    CandidatoResposta,
    NovoCandidato,
    NovoPartido,
    PartidoResposta,
)
from app.compartilhado.banco import obter_sessao
from app.compartilhado.openapi import respostas_de_erro
from app.compartilhado.paginacao import Pagina, Paginacao, obter_paginacao
from app.compartilhado.relogio import obter_agora

# `identidade.dependencias` é a única parte de `identidade` (além do serviço) que as rotas de
# outros módulos podem importar (seção 5).
from app.identidade.dependencias import (
    Perfil,
    UsuarioAutenticado,
    exige_perfil,
    obter_usuario_atual,
)

roteador = APIRouter()

somente_chefe = [Depends(exige_perfil(Perfil.CHEFE_SECAO))]
IdDoCandidato = Annotated[int, Path(gt=0, description="Identificador do candidato.")]


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidatoResposta:
    candidato = servico.cadastrar_candidato(sessao, NovoCandidatoDados(**dados.model_dump()), agora)
    return CandidatoResposta.model_validate(candidato)


@roteador.get(
    "/candidatos",
    response_model=Pagina[CandidatoResposta],
    dependencies=somente_chefe,
    tags=["Candidatos"],
    summary="Lista os candidatos",
    description="Ordenados por nome, com filtro opcional por parte do nome e paginação (RN-30).",
    responses=respostas_de_erro(401, 403, 422),
)
def listar_candidatos(
    sessao: Annotated[Session, Depends(obter_sessao)],
    paginacao: Annotated[Paginacao, Depends(obter_paginacao)],
    nome: Annotated[
        str | None, Query(max_length=120, description="Parte do nome, sem diferenciar maiúsculas.")
    ] = None,
) -> Pagina[CandidatoResposta]:
    pagina = servico.listar_candidatos(sessao, nome, paginacao)
    return Pagina[CandidatoResposta](
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
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> CandidatoResposta:
    return CandidatoResposta.model_validate(servico.obter_candidato_logado(sessao, usuario.id))


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
    candidato_id: IdDoCandidato, sessao: Annotated[Session, Depends(obter_sessao)]
) -> CandidatoResposta:
    return CandidatoResposta.model_validate(servico.obter_candidato(sessao, candidato_id))


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
    sessao: Annotated[Session, Depends(obter_sessao)],
    agora: Annotated[datetime, Depends(obter_agora)],
) -> CandidatoResposta:
    candidato = servico.atualizar_candidato(
        sessao, candidato_id, AlteracoesCandidato(**alteracao.model_dump()), agora
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
def excluir_candidato(
    candidato_id: IdDoCandidato, sessao: Annotated[Session, Depends(obter_sessao)]
) -> Response:
    servico.excluir_candidato(sessao, candidato_id)
    return Response(status_code=204)


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
