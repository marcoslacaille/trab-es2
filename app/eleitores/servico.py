"""Casos de uso de eleitores. É a única porta de entrada do módulo para os outros.

O nome e o CPF do eleitor ficam na credencial: este módulo os pede a `identidade.servico` e
nunca lê a tabela `usuarios`. As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.compartilhado.erros import ConflitoDeEstado, NaoEncontrado
from app.eleitores import repositorio
from app.eleitores.dominio import (
    EleitorDetalhado,
    NovoEleitorDados,
    validar_idade_eleitor,
    validar_titulo_eleitor,
)
from app.eleitores.modelos import Eleitor

# Um módulo só importa `servico` de outro (seção 5). `Perfil` e `UsuarioAutenticado` chegam
# por aí porque `identidade.servico` já os importa de seu `dominio`.
from app.identidade import servico as servico_identidade


def _detalhar(eleitor: Eleitor, usuario: servico_identidade.UsuarioAutenticado) -> EleitorDetalhado:
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
    eleitor = repositorio.buscar_por_id(sessao, eleitor_id)
    if eleitor is None:
        raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
    return eleitor


def _com_credencial(sessao: Session, eleitor: Eleitor) -> EleitorDetalhado:
    """Completa o eleitor com a credencial. Credencial ausente é inconsistência interna (500)."""
    usuarios = servico_identidade.obter_usuarios(sessao, [eleitor.usuario_id])
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
    if repositorio.buscar_por_titulo(sessao, dados.titulo_eleitor) is not None:
        raise ConflitoDeEstado(
            "Já existe um eleitor com este título de eleitor.", codigo="TITULO_JA_CADASTRADO"
        )

    usuario_id = servico_identidade.criar_credencial(
        sessao, dados.cpf, dados.nome, dados.senha, servico_identidade.Perfil.ELEITOR, agora
    )
    eleitor = Eleitor(
        usuario_id=usuario_id,
        titulo_eleitor=dados.titulo_eleitor,
        data_nascimento=dados.data_nascimento,
        criado_em=agora,
    )
    repositorio.inserir(sessao, eleitor)
    sessao.commit()
    return _com_credencial(sessao, eleitor)
