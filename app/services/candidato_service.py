"""Service de candidatos: casos de uso e transação, com as regras de nome de urna e nascimento.

O nome e o CPF do candidato ficam na credencial: o service os pede ao `UsuarioService` e nunca
lê a tabela `usuarios`. Os métodos chamados pelas rotas fazem `commit` no final.
"""

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos, NaoEncontrado, nome_da_restricao
from app.core.paginacao import Pagina, Paginacao
from app.dto.candidato_dto import (
    AlteracoesCandidato,
    CandidatoDetalhado,
    CandidatoResumo,
    NovoCandidatoDados,
)
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.candidato import Candidato
from app.models.enums import Perfil
from app.repositories.candidato_repository import CandidatoRepository
from app.services.usuario_service import UsuarioService

NOME_DE_URNA_MINIMO = 3
NOME_DE_URNA_MAXIMO = 30

# Restrição que impede apagar quem tem candidatura (a tabela nasce na migração 0004).
FK_CANDIDATO_COM_CANDIDATURA = "fk_candidaturas_candidato_id_candidatos"


def validar_nome_de_urna(nome_urna: str) -> str:
    """RN-31: o nome de urna tem de 3 a 30 caracteres, sem contar espaços nas pontas.

    Devolve o nome sem os espaços das pontas. Levanta `DadosInvalidos` com o código
    `DADOS_INVALIDOS` (422) se o tamanho não servir.
    """
    nome_urna = nome_urna.strip()
    if not NOME_DE_URNA_MINIMO <= len(nome_urna) <= NOME_DE_URNA_MAXIMO:
        raise DadosInvalidos(
            f"O nome de urna deve ter de {NOME_DE_URNA_MINIMO} a {NOME_DE_URNA_MAXIMO} caracteres.",
            codigo="DADOS_INVALIDOS",
        )
    return nome_urna


def validar_nascimento_do_candidato(data_nascimento: date, hoje: date) -> None:
    """RN-31: a data de nascimento do candidato precisa estar no passado.

    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se for hoje ou futura.
    """
    if data_nascimento >= hoje:
        raise DadosInvalidos(
            "A data de nascimento deve estar no passado.", codigo="DADOS_INVALIDOS"
        )


class CandidatoService:
    """Service de candidatos: casos de uso e transação."""

    def __init__(
        self,
        sessao: Session,
        repository: CandidatoRepository | None = None,
        usuarios: UsuarioService | None = None,
    ) -> None:
        self.sessao = sessao
        self.repository = repository or CandidatoRepository(sessao)
        self.usuarios = usuarios or UsuarioService(sessao)

    @staticmethod
    def _detalhar(candidato: Candidato, usuario: UsuarioAutenticado) -> CandidatoDetalhado:
        """Junta os dados do candidato com nome e CPF da credencial. O ORM não sai do service."""
        return CandidatoDetalhado(
            id=candidato.id,
            usuario_id=candidato.usuario_id,
            nome=usuario.nome,
            nome_urna=candidato.nome_urna,
            cpf=usuario.cpf,
            data_nascimento=candidato.data_nascimento,
            criado_em=candidato.criado_em,
        )

    @staticmethod
    def _resumir_candidato(candidato: Candidato) -> CandidatoResumo:
        """Converte o modelo no resumo do domínio. O ORM não sai do service."""
        return CandidatoResumo(
            id=candidato.id,
            usuario_id=candidato.usuario_id,
            nome_urna=candidato.nome_urna,
            data_nascimento=candidato.data_nascimento,
        )

    def _obter_modelo(self, candidato_id: int) -> Candidato:
        """Busca o candidato ou levanta 404 `CANDIDATO_NAO_ENCONTRADO`."""
        candidato = self.repository.buscar_candidato_por_id(candidato_id)
        if candidato is None:
            raise NaoEncontrado("Candidato não encontrado.", codigo="CANDIDATO_NAO_ENCONTRADO")
        return candidato

    def _com_credencial(self, candidato: Candidato) -> CandidatoDetalhado:
        """Completa o candidato com a credencial. Credencial ausente é inconsistência (500)."""
        usuarios = self.usuarios.obter_usuarios([candidato.usuario_id])
        usuario = usuarios.get(candidato.usuario_id)
        if usuario is None:
            raise LookupError(f"O candidato {candidato.id} não tem credencial.")
        return self._detalhar(candidato, usuario)

    def cadastrar_candidato(self, dados: NovoCandidatoDados, agora: datetime) -> CandidatoDetalhado:
        """Cadastra o candidato junto com a credencial dele e faz commit (RN-31).

        RN-31: nome de urna de 3 a 30 caracteres e nascimento no passado (`DADOS_INVALIDOS`, 422).
        RN-07, RN-08 e RN-05: CPF, nome e senha são conferidos por
        `UsuarioService.criar_credencial`, na mesma transação: se algo falhar, nada fica gravado
        pela metade.
        """
        nome_urna = validar_nome_de_urna(dados.nome_urna)
        validar_nascimento_do_candidato(dados.data_nascimento, agora.date())

        usuario_id = self.usuarios.criar_credencial(
            dados.cpf, dados.nome, dados.senha, Perfil.CANDIDATO, agora
        )
        candidato = Candidato(
            usuario_id=usuario_id,
            nome_urna=nome_urna,
            data_nascimento=dados.data_nascimento,
            criado_em=agora,
        )
        self.repository.inserir_candidato(candidato)
        self.sessao.commit()
        return self._com_credencial(candidato)

    def listar_candidatos(
        self, nome: str | None, paginacao: Paginacao
    ) -> Pagina[CandidatoDetalhado]:
        """Lista os candidatos, filtrando por parte do nome e ordenados por nome (RN-30).

        A paginação e o filtro de nome ficam com `UsuarioService.listar_usuarios`; aqui só se
        buscam, numa única consulta, os candidatos desses usuários.
        """
        usuarios = self.usuarios.listar_usuarios(Perfil.CANDIDATO, nome, paginacao)
        candidatos = self.repository.buscar_candidatos_por_usuarios_ids(
            [u.id for u in usuarios.itens]
        )
        por_usuario = {candidato.usuario_id: candidato for candidato in candidatos}
        return Pagina[CandidatoDetalhado](
            itens=[
                self._detalhar(por_usuario[u.id], u) for u in usuarios.itens if u.id in por_usuario
            ],
            pagina=usuarios.pagina,
            tamanho=usuarios.tamanho,
            total=usuarios.total,
        )

    def obter_candidato(self, candidato_id: int) -> CandidatoDetalhado:
        """Consulta um candidato (RN-30). Levanta 404 `CANDIDATO_NAO_ENCONTRADO` se não existir."""
        return self._com_credencial(self._obter_modelo(candidato_id))

    def atualizar_candidato(
        self, candidato_id: int, alteracoes: AlteracoesCandidato, agora: datetime
    ) -> CandidatoDetalhado:
        """Altera nome, nome de urna, nascimento e/ou senha do candidato e faz commit (RN-31).

        Nome e senha vão para `UsuarioService.atualizar_credencial` (RN-08 e RN-05). O CPF nunca
        muda (RN-33).
        """
        candidato = self._obter_modelo(candidato_id)
        if alteracoes.nome_urna is not None:
            candidato.nome_urna = validar_nome_de_urna(alteracoes.nome_urna)
        if alteracoes.data_nascimento is not None:
            validar_nascimento_do_candidato(alteracoes.data_nascimento, agora.date())
            candidato.data_nascimento = alteracoes.data_nascimento
        if alteracoes.nome is not None or alteracoes.senha is not None:
            self.usuarios.atualizar_credencial(
                candidato.usuario_id, agora, nome=alteracoes.nome, senha=alteracoes.senha
            )
        self.sessao.commit()
        return self._com_credencial(candidato)

    def excluir_candidato(self, candidato_id: int) -> None:
        """Exclui o candidato e a credencial dele, e faz commit (RN-33).

        Quem tem candidatura não pode ser excluído: a chave estrangeira de `candidaturas` bloqueia
        e o erro vira 409 `EXCLUSAO_BLOQUEADA`. Candidato inexistente dá 404
        `CANDIDATO_NAO_ENCONTRADO`.
        """
        candidato = self._obter_modelo(candidato_id)
        usuario_id = candidato.usuario_id
        try:
            self.repository.remover_candidato(candidato)
        except IntegrityError as erro:
            self.sessao.rollback()
            if nome_da_restricao(erro) != FK_CANDIDATO_COM_CANDIDATURA:
                raise
            raise ConflitoDeEstado(
                "O candidato tem candidaturas. Remova as candidaturas antes.",
                codigo="EXCLUSAO_BLOQUEADA",
            ) from erro
        self.usuarios.remover_credencial(usuario_id)
        self.sessao.commit()

    def obter_candidato_logado(self, usuario_id: int) -> CandidatoDetalhado:
        """Os dados completos do próprio candidato, para `/candidatos/eu` (RN-30).

        Levanta 404 `CANDIDATO_NAO_ENCONTRADO` se a credencial não tiver um candidato.
        """
        candidato = self.repository.buscar_candidato_por_usuario_id(usuario_id)
        if candidato is None:
            raise NaoEncontrado("Candidato não encontrado.", codigo="CANDIDATO_NAO_ENCONTRADO")
        return self._com_credencial(candidato)

    def obter_candidato_do_usuario(self, usuario_id: int) -> CandidatoResumo | None:
        """Devolve o candidato dono desta credencial, ou `None` se não houver.

        Usada pelo `EleicaoService`.
        """
        candidato = self.repository.buscar_candidato_por_usuario_id(usuario_id)
        return self._resumir_candidato(candidato) if candidato else None

    def obter_resumos_de_candidatos(self, ids: list[int]) -> dict[int, CandidatoResumo]:
        """Resumos dos candidatos que existem, indexados pelo id (ids inexistentes ficam de fora).

        Usada pelo `EleicaoService` para montar a lista de candidaturas numa única consulta.
        """
        if not ids:
            return {}
        candidatos = self.repository.buscar_candidatos_por_ids(ids)
        return {candidato.id: self._resumir_candidato(candidato) for candidato in candidatos}
