"""Service de eleitores: casos de uso e transação, com as regras de idade e de título.

O nome e o CPF do eleitor ficam na credencial: o service os pede ao `UsuarioService` e nunca
lê a tabela `usuarios`. Os métodos chamados pelas rotas fazem `commit` no final.
"""

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos, NaoEncontrado, nome_da_restricao
from app.core.paginacao import Pagina, Paginacao
from app.core.validadores import calcular_idade, so_digitos
from app.dto.eleitor_dto import (
    AlteracoesEleitor,
    EleitorDetalhado,
    EleitorResumo,
    NovoEleitorDados,
)
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.eleitor import Eleitor
from app.models.enums import Perfil
from app.repositories.eleitor_repository import EleitorRepository
from app.services.usuario_service import UsuarioService

IDADE_MINIMA_ELEITOR = 16
DIGITOS_DO_TITULO = 12

# Restrição que impede apagar quem já votou (a tabela nasce na migração 0005).
FK_ELEITOR_JA_VOTOU = "fk_registros_votacao_eleitor_id_eleitores"


def validar_idade_eleitor(data_nascimento: date, hoje: date) -> None:
    """RN-22: o eleitor precisa ter nascido no passado e ter 16 anos completos em `hoje`.

    Levanta `DadosInvalidos` com o código `IDADE_MINIMA` (422) nos dois casos.
    """
    if data_nascimento >= hoje:
        raise DadosInvalidos("A data de nascimento deve estar no passado.", codigo="IDADE_MINIMA")
    if calcular_idade(data_nascimento, hoje) < IDADE_MINIMA_ELEITOR:
        raise DadosInvalidos(
            f"O eleitor deve ter pelo menos {IDADE_MINIMA_ELEITOR} anos.", codigo="IDADE_MINIMA"
        )


def validar_titulo_eleitor(titulo_eleitor: str) -> None:
    """RN-21: o título tem exatamente 12 dígitos (0 a 9).

    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se não tiver.
    """
    if len(titulo_eleitor) != DIGITOS_DO_TITULO or not so_digitos(titulo_eleitor):
        raise DadosInvalidos(
            f"O título de eleitor deve ter {DIGITOS_DO_TITULO} dígitos.",
            codigo="DADOS_INVALIDOS",
        )


class EleitorService:
    """Service de eleitores: casos de uso e transação."""

    def __init__(
        self,
        sessao: Session,
        repository: EleitorRepository | None = None,
        usuarios: UsuarioService | None = None,
    ) -> None:
        self.sessao = sessao
        self.repository = repository or EleitorRepository(sessao)
        self.usuarios = usuarios or UsuarioService(sessao)

    @staticmethod
    def _detalhar(eleitor: Eleitor, usuario: UsuarioAutenticado) -> EleitorDetalhado:
        """Junta os dados do eleitor com nome e CPF da credencial. O ORM não sai do service."""
        return EleitorDetalhado(
            id=eleitor.id,
            usuario_id=eleitor.usuario_id,
            nome=usuario.nome,
            cpf=usuario.cpf,
            titulo_eleitor=eleitor.titulo_eleitor,
            data_nascimento=eleitor.data_nascimento,
            criado_em=eleitor.criado_em,
        )

    def _obter_modelo(self, eleitor_id: int) -> Eleitor:
        """Busca o eleitor ou levanta 404 `ELEITOR_NAO_ENCONTRADO`."""
        eleitor = self.repository.buscar_por_id(eleitor_id)
        if eleitor is None:
            raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
        return eleitor

    def _com_credencial(self, eleitor: Eleitor) -> EleitorDetalhado:
        """Completa o eleitor com a credencial. Credencial ausente é inconsistência (500)."""
        usuarios = self.usuarios.obter_usuarios([eleitor.usuario_id])
        usuario = usuarios.get(eleitor.usuario_id)
        if usuario is None:
            raise LookupError(f"O eleitor {eleitor.id} não tem credencial.")
        return self._detalhar(eleitor, usuario)

    def cadastrar_eleitor(self, dados: NovoEleitorDados, agora: datetime) -> EleitorDetalhado:
        """Cadastra o eleitor junto com a credencial dele e faz commit (RN-20 a RN-22).

        RN-22: 16 anos completos e nascimento no passado (`IDADE_MINIMA`, 422).
        RN-21: título com 12 dígitos (`DADOS_INVALIDOS`, 422) e único (`TITULO_JA_CADASTRADO`, 409).
        RN-07 e RN-05: CPF e senha são conferidos por `UsuarioService.criar_credencial`, na mesma
        transação: se algo falhar, nada fica gravado pela metade.
        """
        validar_idade_eleitor(dados.data_nascimento, agora.date())
        validar_titulo_eleitor(dados.titulo_eleitor)
        if self.repository.buscar_por_titulo(dados.titulo_eleitor) is not None:
            raise ConflitoDeEstado(
                "Já existe um eleitor com este título de eleitor.", codigo="TITULO_JA_CADASTRADO"
            )

        usuario_id = self.usuarios.criar_credencial(
            dados.cpf, dados.nome, dados.senha, Perfil.ELEITOR, agora
        )
        eleitor = Eleitor(
            usuario_id=usuario_id,
            titulo_eleitor=dados.titulo_eleitor,
            data_nascimento=dados.data_nascimento,
            criado_em=agora,
        )
        self.repository.inserir(eleitor)
        self.sessao.commit()
        return self._com_credencial(eleitor)

    def listar_eleitores(self, nome: str | None, paginacao: Paginacao) -> Pagina[EleitorDetalhado]:
        """Lista os eleitores, filtrando por parte do nome e ordenados por nome (RN-20).

        A paginação e o filtro de nome ficam com `UsuarioService.listar_usuarios`; aqui só se
        buscam, numa única consulta, os eleitores desses usuários.
        """
        usuarios = self.usuarios.listar_usuarios(Perfil.ELEITOR, nome, paginacao)
        eleitores = self.repository.buscar_por_usuarios_ids([u.id for u in usuarios.itens])
        por_usuario = {eleitor.usuario_id: eleitor for eleitor in eleitores}
        return Pagina[EleitorDetalhado](
            itens=[
                self._detalhar(por_usuario[u.id], u) for u in usuarios.itens if u.id in por_usuario
            ],
            pagina=usuarios.pagina,
            tamanho=usuarios.tamanho,
            total=usuarios.total,
        )

    def obter_eleitor(self, eleitor_id: int) -> EleitorDetalhado:
        """Consulta um eleitor (RN-20). Levanta 404 `ELEITOR_NAO_ENCONTRADO` se não existir."""
        return self._com_credencial(self._obter_modelo(eleitor_id))

    def atualizar_eleitor(
        self, eleitor_id: int, alteracoes: AlteracoesEleitor, agora: datetime
    ) -> EleitorDetalhado:
        """Altera nome, data de nascimento e/ou senha do eleitor e faz commit (RN-23).

        RN-22: uma nova data de nascimento passa pela regra de idade mínima. Nome e senha vão para
        `UsuarioService.atualizar_credencial` (RN-08 e RN-05). CPF e título nunca mudam.
        """
        eleitor = self._obter_modelo(eleitor_id)
        if alteracoes.data_nascimento is not None:
            validar_idade_eleitor(alteracoes.data_nascimento, agora.date())
            eleitor.data_nascimento = alteracoes.data_nascimento
        if alteracoes.nome is not None or alteracoes.senha is not None:
            self.usuarios.atualizar_credencial(
                eleitor.usuario_id, agora, nome=alteracoes.nome, senha=alteracoes.senha
            )
        self.sessao.commit()
        return self._com_credencial(eleitor)

    def excluir_eleitor(self, eleitor_id: int) -> None:
        """Exclui o eleitor e a credencial dele, e faz commit (RN-24).

        Quem já votou não pode ser excluído: a chave estrangeira de `registros_votacao` bloqueia e
        o erro vira 409 `EXCLUSAO_BLOQUEADA`. Eleitor inexistente dá 404 `ELEITOR_NAO_ENCONTRADO`.
        """
        eleitor = self._obter_modelo(eleitor_id)
        usuario_id = eleitor.usuario_id
        try:
            self.repository.remover(eleitor)
        except IntegrityError as erro:
            self.sessao.rollback()
            if nome_da_restricao(erro) != FK_ELEITOR_JA_VOTOU:
                raise
            raise ConflitoDeEstado(
                "O eleitor já votou e não pode ser excluído.", codigo="EXCLUSAO_BLOQUEADA"
            ) from erro
        self.usuarios.remover_credencial(usuario_id)
        self.sessao.commit()

    def obter_eleitor_do_usuario(self, usuario_id: int) -> EleitorResumo | None:
        """Devolve o eleitor dono desta credencial, ou `None` se não houver.

        Usada pelo `VotacaoService`.
        """
        eleitor = self.repository.buscar_por_usuario_id(usuario_id)
        if eleitor is None:
            return None
        return EleitorResumo(
            id=eleitor.id, usuario_id=eleitor.usuario_id, criado_em=eleitor.criado_em
        )

    def obter_eleitor_logado(self, usuario_id: int) -> EleitorDetalhado:
        """Os dados completos do próprio eleitor, para `/eleitores/eu` (RN-25).

        Levanta 404 `ELEITOR_NAO_ENCONTRADO` se a credencial não tiver um eleitor.
        """
        eleitor = self.repository.buscar_por_usuario_id(usuario_id)
        if eleitor is None:
            raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
        return self._com_credencial(eleitor)

    def contar_aptos(self, ate: datetime) -> int:
        """Quantos eleitores estavam cadastrados até o instante `ate`, inclusive (RN-79).

        Usada pelo `ApuracaoService` com o instante da abertura da eleição.
        """
        return self.repository.contar_cadastrados_ate(ate)
