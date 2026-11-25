"""Service de eleitores: casos de uso e transação. Única porta de entrada do módulo.

O nome e o CPF do eleitor ficam na credencial: este módulo os pede a `identidade.service` e
nunca lê a tabela `usuarios`. As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflitoDeEstado, NaoEncontrado, nome_da_restricao
from app.core.paginacao import Pagina, Paginacao
from app.dto.eleitor_dto import (
    AlteracoesEleitor,
    EleitorDetalhado,
    EleitorResumo,
    NovoEleitorDados,
)
from app.dto.usuario_dto import UsuarioAutenticado
from app.eleitores.dominio import validar_idade_eleitor, validar_titulo_eleitor
from app.models.eleitor import Eleitor
from app.models.enums import Perfil
from app.repositories.eleitor_repository import EleitorRepository
from app.services.usuario_service import UsuarioService

# Restrição que impede apagar quem já votou (a tabela nasce na migração 0005).
FK_ELEITOR_JA_VOTOU = "fk_registros_votacao_eleitor_id_eleitores"


def _detalhar(eleitor: Eleitor, usuario: UsuarioAutenticado) -> EleitorDetalhado:
    """Junta os dados do eleitor com nome e CPF da credencial. O ORM não sai do módulo."""
    return EleitorDetalhado(
        id=eleitor.id,
        usuario_id=eleitor.usuario_id,
        nome=usuario.nome,
        cpf=usuario.cpf,
        titulo_eleitor=eleitor.titulo_eleitor,
        data_nascimento=eleitor.data_nascimento,
        criado_em=eleitor.criado_em,
    )


def _obter_modelo(sessao: Session, eleitor_id: int) -> Eleitor:
    """Busca o eleitor ou levanta 404 `ELEITOR_NAO_ENCONTRADO`."""
    eleitor = EleitorRepository(sessao).buscar_por_id(eleitor_id)
    if eleitor is None:
        raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
    return eleitor


def _com_credencial(sessao: Session, eleitor: Eleitor) -> EleitorDetalhado:
    """Completa o eleitor com a credencial. Credencial ausente é inconsistência interna (500)."""
    usuarios = UsuarioService(sessao).obter_usuarios([eleitor.usuario_id])
    usuario = usuarios.get(eleitor.usuario_id)
    if usuario is None:
        raise LookupError(f"O eleitor {eleitor.id} não tem credencial.")
    return _detalhar(eleitor, usuario)


def cadastrar_eleitor(
    sessao: Session, dados: NovoEleitorDados, agora: datetime
) -> EleitorDetalhado:
    """Cadastra o eleitor junto com a credencial dele e faz commit (RN-20 a RN-22).

    RN-22: 16 anos completos e nascimento no passado (`IDADE_MINIMA`, 422).
    RN-21: título com 12 dígitos (`DADOS_INVALIDOS`, 422) e único (`TITULO_JA_CADASTRADO`, 409).
    RN-07 e RN-05: CPF e senha são conferidos por `identidade.criar_credencial`, na mesma
    transação: se algo falhar, nada fica gravado pela metade.
    """
    validar_idade_eleitor(dados.data_nascimento, agora.date())
    validar_titulo_eleitor(dados.titulo_eleitor)
    if EleitorRepository(sessao).buscar_por_titulo(dados.titulo_eleitor) is not None:
        raise ConflitoDeEstado(
            "Já existe um eleitor com este título de eleitor.", codigo="TITULO_JA_CADASTRADO"
        )

    usuario_id = UsuarioService(sessao).criar_credencial(
        dados.cpf, dados.nome, dados.senha, Perfil.ELEITOR, agora
    )
    eleitor = Eleitor(
        usuario_id=usuario_id,
        titulo_eleitor=dados.titulo_eleitor,
        data_nascimento=dados.data_nascimento,
        criado_em=agora,
    )
    EleitorRepository(sessao).inserir(eleitor)
    sessao.commit()
    return _com_credencial(sessao, eleitor)


def listar_eleitores(
    sessao: Session, nome: str | None, paginacao: Paginacao
) -> Pagina[EleitorDetalhado]:
    """Lista os eleitores, filtrando por parte do nome e ordenados por nome (RN-20).

    A paginação e o filtro de nome ficam com `identidade.listar_usuarios`; aqui só se buscam,
    numa única consulta, os eleitores desses usuários.
    """
    usuarios = UsuarioService(sessao).listar_usuarios(Perfil.ELEITOR, nome, paginacao)
    eleitores = EleitorRepository(sessao).buscar_por_usuarios_ids([u.id for u in usuarios.itens])
    por_usuario = {eleitor.usuario_id: eleitor for eleitor in eleitores}
    return Pagina[EleitorDetalhado](
        itens=[_detalhar(por_usuario[u.id], u) for u in usuarios.itens if u.id in por_usuario],
        pagina=usuarios.pagina,
        tamanho=usuarios.tamanho,
        total=usuarios.total,
    )


def obter_eleitor(sessao: Session, eleitor_id: int) -> EleitorDetalhado:
    """Consulta um eleitor (RN-20). Levanta 404 `ELEITOR_NAO_ENCONTRADO` se não existir."""
    return _com_credencial(sessao, _obter_modelo(sessao, eleitor_id))


def atualizar_eleitor(
    sessao: Session, eleitor_id: int, alteracoes: AlteracoesEleitor, agora: datetime
) -> EleitorDetalhado:
    """Altera nome, data de nascimento e/ou senha do eleitor e faz commit (RN-23).

    RN-22: uma nova data de nascimento passa pela regra de idade mínima. Nome e senha vão para
    `identidade.atualizar_credencial` (RN-08 e RN-05). CPF e título nunca mudam.
    """
    eleitor = _obter_modelo(sessao, eleitor_id)
    if alteracoes.data_nascimento is not None:
        validar_idade_eleitor(alteracoes.data_nascimento, agora.date())
        eleitor.data_nascimento = alteracoes.data_nascimento
    if alteracoes.nome is not None or alteracoes.senha is not None:
        UsuarioService(sessao).atualizar_credencial(
            eleitor.usuario_id, agora, nome=alteracoes.nome, senha=alteracoes.senha
        )
    sessao.commit()
    return _com_credencial(sessao, eleitor)


def excluir_eleitor(sessao: Session, eleitor_id: int) -> None:
    """Exclui o eleitor e a credencial dele, e faz commit (RN-24).

    Quem já votou não pode ser excluído: a chave estrangeira de `registros_votacao` bloqueia e
    o erro vira 409 `EXCLUSAO_BLOQUEADA`. Eleitor inexistente dá 404 `ELEITOR_NAO_ENCONTRADO`.
    """
    eleitor = _obter_modelo(sessao, eleitor_id)
    usuario_id = eleitor.usuario_id
    try:
        EleitorRepository(sessao).remover(eleitor)
    except IntegrityError as erro:
        sessao.rollback()
        if nome_da_restricao(erro) != FK_ELEITOR_JA_VOTOU:
            raise
        raise ConflitoDeEstado(
            "O eleitor já votou e não pode ser excluído.", codigo="EXCLUSAO_BLOQUEADA"
        ) from erro
    UsuarioService(sessao).remover_credencial(usuario_id)
    sessao.commit()


def obter_eleitor_do_usuario(sessao: Session, usuario_id: int) -> EleitorResumo | None:
    """Devolve o eleitor dono desta credencial, ou `None` se não houver. Usada por `votacao`."""
    eleitor = EleitorRepository(sessao).buscar_por_usuario_id(usuario_id)
    if eleitor is None:
        return None
    return EleitorResumo(id=eleitor.id, usuario_id=eleitor.usuario_id, criado_em=eleitor.criado_em)


def obter_eleitor_logado(sessao: Session, usuario_id: int) -> EleitorDetalhado:
    """Os dados completos do próprio eleitor, para `/eleitores/eu` (RN-25).

    Levanta 404 `ELEITOR_NAO_ENCONTRADO` se a credencial não tiver um eleitor.
    """
    eleitor = EleitorRepository(sessao).buscar_por_usuario_id(usuario_id)
    if eleitor is None:
        raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
    return _com_credencial(sessao, eleitor)


def contar_aptos(sessao: Session, ate: datetime) -> int:
    """Quantos eleitores estavam cadastrados até o instante `ate`, inclusive (RN-79).

    Usada por `apuracao` com o instante da abertura da eleição.
    """
    return EleitorRepository(sessao).contar_cadastrados_ate(ate)
