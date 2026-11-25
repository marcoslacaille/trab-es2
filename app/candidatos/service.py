"""Service de candidatos e partidos: casos de uso e transação. Única porta de entrada do módulo.

O nome e o CPF do candidato ficam na credencial: este módulo os pede a `identidade.service` e
nunca lê a tabela `usuarios`. As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.candidatos.dominio import (
    validar_nascimento_do_candidato,
    validar_nome_de_urna,
    validar_partido,
)
from app.core.exceptions import ConflitoDeEstado, NaoEncontrado, nome_da_restricao
from app.core.paginacao import Pagina, Paginacao
from app.dto.candidato_dto import (
    AlteracoesCandidato,
    CandidatoDetalhado,
    CandidatoResumo,
    NovoCandidatoDados,
)
from app.dto.partido_dto import NovoPartidoDados, PartidoResumo

# Um módulo só importa `service` de outro (seção 5). `UsuarioAutenticado` chega por aí porque
# `identidade.service` já o importa de `dto/usuario_dto` (mesmo caso de `eleitores`).
from app.identidade import service as service_identidade
from app.models.candidato import Candidato
from app.models.enums import Perfil
from app.models.partido import Partido
from app.repositories.candidato_repository import CandidatoRepository
from app.repositories.partido_repository import PartidoRepository

# Restrição que impede apagar quem tem candidatura (a tabela nasce na migração 0004).
FK_CANDIDATO_COM_CANDIDATURA = "fk_candidaturas_candidato_id_candidatos"


def _detalhar(
    candidato: Candidato, usuario: service_identidade.UsuarioAutenticado
) -> CandidatoDetalhado:
    """Junta os dados do candidato com nome e CPF da credencial. O ORM não sai do módulo."""
    return CandidatoDetalhado(
        id=candidato.id,
        usuario_id=candidato.usuario_id,
        nome=usuario.nome,
        nome_urna=candidato.nome_urna,
        cpf=usuario.cpf,
        data_nascimento=candidato.data_nascimento,
        criado_em=candidato.criado_em,
    )


def _resumir_candidato(candidato: Candidato) -> CandidatoResumo:
    """Converte o modelo no resumo do domínio. O ORM não sai do módulo."""
    return CandidatoResumo(
        id=candidato.id,
        usuario_id=candidato.usuario_id,
        nome_urna=candidato.nome_urna,
        data_nascimento=candidato.data_nascimento,
    )


def _resumir_partido(partido: Partido) -> PartidoResumo:
    """Converte o modelo no resumo do domínio. O ORM não sai do módulo."""
    return PartidoResumo(
        id=partido.id, sigla=partido.sigla, nome=partido.nome, numero=partido.numero
    )


def _obter_modelo(sessao: Session, candidato_id: int) -> Candidato:
    """Busca o candidato ou levanta 404 `CANDIDATO_NAO_ENCONTRADO`."""
    candidato = CandidatoRepository(sessao).buscar_candidato_por_id(candidato_id)
    if candidato is None:
        raise NaoEncontrado("Candidato não encontrado.", codigo="CANDIDATO_NAO_ENCONTRADO")
    return candidato


def _com_credencial(sessao: Session, candidato: Candidato) -> CandidatoDetalhado:
    """Completa o candidato com a credencial. Credencial ausente é inconsistência (500)."""
    usuarios = service_identidade.obter_usuarios(sessao, [candidato.usuario_id])
    usuario = usuarios.get(candidato.usuario_id)
    if usuario is None:
        raise LookupError(f"O candidato {candidato.id} não tem credencial.")
    return _detalhar(candidato, usuario)


def cadastrar_candidato(
    sessao: Session, dados: NovoCandidatoDados, agora: datetime
) -> CandidatoDetalhado:
    """Cadastra o candidato junto com a credencial dele e faz commit (RN-31).

    RN-31: nome de urna de 3 a 30 caracteres e nascimento no passado (`DADOS_INVALIDOS`, 422).
    RN-07, RN-08 e RN-05: CPF, nome e senha são conferidos por `identidade.criar_credencial`,
    na mesma transação: se algo falhar, nada fica gravado pela metade.
    """
    nome_urna = validar_nome_de_urna(dados.nome_urna)
    validar_nascimento_do_candidato(dados.data_nascimento, agora.date())

    usuario_id = service_identidade.criar_credencial(
        sessao, dados.cpf, dados.nome, dados.senha, Perfil.CANDIDATO, agora
    )
    candidato = Candidato(
        usuario_id=usuario_id,
        nome_urna=nome_urna,
        data_nascimento=dados.data_nascimento,
        criado_em=agora,
    )
    CandidatoRepository(sessao).inserir_candidato(candidato)
    sessao.commit()
    return _com_credencial(sessao, candidato)


def listar_candidatos(
    sessao: Session, nome: str | None, paginacao: Paginacao
) -> Pagina[CandidatoDetalhado]:
    """Lista os candidatos, filtrando por parte do nome e ordenados por nome (RN-30).

    A paginação e o filtro de nome ficam com `identidade.listar_usuarios`; aqui só se buscam,
    numa única consulta, os candidatos desses usuários.
    """
    usuarios = service_identidade.listar_usuarios(sessao, Perfil.CANDIDATO, nome, paginacao)
    candidatos = CandidatoRepository(sessao).buscar_candidatos_por_usuarios_ids(
        [u.id for u in usuarios.itens]
    )
    por_usuario = {candidato.usuario_id: candidato for candidato in candidatos}
    return Pagina[CandidatoDetalhado](
        itens=[_detalhar(por_usuario[u.id], u) for u in usuarios.itens if u.id in por_usuario],
        pagina=usuarios.pagina,
        tamanho=usuarios.tamanho,
        total=usuarios.total,
    )


def obter_candidato(sessao: Session, candidato_id: int) -> CandidatoDetalhado:
    """Consulta um candidato (RN-30). Levanta 404 `CANDIDATO_NAO_ENCONTRADO` se não existir."""
    return _com_credencial(sessao, _obter_modelo(sessao, candidato_id))


def atualizar_candidato(
    sessao: Session, candidato_id: int, alteracoes: AlteracoesCandidato, agora: datetime
) -> CandidatoDetalhado:
    """Altera nome, nome de urna, nascimento e/ou senha do candidato e faz commit (RN-31).

    Nome e senha vão para `identidade.atualizar_credencial` (RN-08 e RN-05). O CPF nunca muda
    (RN-33).
    """
    candidato = _obter_modelo(sessao, candidato_id)
    if alteracoes.nome_urna is not None:
        candidato.nome_urna = validar_nome_de_urna(alteracoes.nome_urna)
    if alteracoes.data_nascimento is not None:
        validar_nascimento_do_candidato(alteracoes.data_nascimento, agora.date())
        candidato.data_nascimento = alteracoes.data_nascimento
    if alteracoes.nome is not None or alteracoes.senha is not None:
        service_identidade.atualizar_credencial(
            sessao, candidato.usuario_id, agora, nome=alteracoes.nome, senha=alteracoes.senha
        )
    sessao.commit()
    return _com_credencial(sessao, candidato)


def excluir_candidato(sessao: Session, candidato_id: int) -> None:
    """Exclui o candidato e a credencial dele, e faz commit (RN-33).

    Quem tem candidatura não pode ser excluído: a chave estrangeira de `candidaturas` bloqueia e
    o erro vira 409 `EXCLUSAO_BLOQUEADA`. Candidato inexistente dá 404 `CANDIDATO_NAO_ENCONTRADO`.
    """
    candidato = _obter_modelo(sessao, candidato_id)
    usuario_id = candidato.usuario_id
    try:
        CandidatoRepository(sessao).remover_candidato(candidato)
    except IntegrityError as erro:
        sessao.rollback()
        if nome_da_restricao(erro) != FK_CANDIDATO_COM_CANDIDATURA:
            raise
        raise ConflitoDeEstado(
            "O candidato tem candidaturas. Remova as candidaturas antes.",
            codigo="EXCLUSAO_BLOQUEADA",
        ) from erro
    service_identidade.remover_credencial(sessao, usuario_id)
    sessao.commit()


def obter_candidato_logado(sessao: Session, usuario_id: int) -> CandidatoDetalhado:
    """Os dados completos do próprio candidato, para `/candidatos/eu` (RN-30).

    Levanta 404 `CANDIDATO_NAO_ENCONTRADO` se a credencial não tiver um candidato.
    """
    candidato = CandidatoRepository(sessao).buscar_candidato_por_usuario_id(usuario_id)
    if candidato is None:
        raise NaoEncontrado("Candidato não encontrado.", codigo="CANDIDATO_NAO_ENCONTRADO")
    return _com_credencial(sessao, candidato)


def obter_candidato_do_usuario(sessao: Session, usuario_id: int) -> CandidatoResumo | None:
    """Devolve o candidato dono desta credencial, ou `None` se não houver. Usada por `eleicoes`."""
    candidato = CandidatoRepository(sessao).buscar_candidato_por_usuario_id(usuario_id)
    return _resumir_candidato(candidato) if candidato else None


def obter_resumos_de_candidatos(sessao: Session, ids: list[int]) -> dict[int, CandidatoResumo]:
    """Resumos dos candidatos que existem, indexados pelo id (ids inexistentes ficam de fora).

    Usada por `eleicoes` para montar a lista de candidaturas numa única consulta.
    """
    if not ids:
        return {}
    candidatos = CandidatoRepository(sessao).buscar_candidatos_por_ids(ids)
    return {candidato.id: _resumir_candidato(candidato) for candidato in candidatos}


def criar_partido(sessao: Session, dados: NovoPartidoDados, agora: datetime) -> PartidoResumo:
    """Cadastra um partido e faz commit (RN-32).

    A sigla é gravada em maiúsculas. Sigla, nome ou número já existentes dão 409
    `PARTIDO_DUPLICADO`; dados fora do formato dão 422 `DADOS_INVALIDOS`.
    """
    dados = validar_partido(dados)
    if PartidoRepository(sessao).existe_partido_com(dados.sigla, dados.nome, dados.numero):
        raise ConflitoDeEstado(
            "Já existe um partido com esta sigla, nome ou número.", codigo="PARTIDO_DUPLICADO"
        )
    partido = Partido(sigla=dados.sigla, nome=dados.nome, numero=dados.numero, criado_em=agora)
    PartidoRepository(sessao).inserir_partido(partido)
    sessao.commit()
    return _resumir_partido(partido)


def listar_partidos(sessao: Session) -> list[PartidoResumo]:
    """Todos os partidos, ordenados por número (RN-30: qualquer usuário logado pode listar)."""
    return [
        _resumir_partido(partido)
        for partido in PartidoRepository(sessao).listar_partidos_por_numero()
    ]


def obter_partido(sessao: Session, partido_id: int) -> PartidoResumo | None:
    """Devolve o partido ou `None` se não existir. Usada por `eleicoes` (RN-46)."""
    partido = PartidoRepository(sessao).buscar_partido_por_id(partido_id)
    return _resumir_partido(partido) if partido else None
