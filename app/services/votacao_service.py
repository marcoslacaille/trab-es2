"""Service de votação: cédula, prévia e confirmação do voto, com o sigilo e a transação.

`registrar_voto` só confere; `confirmar_voto` grava nas duas tabelas sem ligação entre si (RN-60).
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cedula import emitir_cedula, ler_cedula
from app.core.exceptions import (
    AcessoNegado,
    ConflitoDeEstado,
    DadosInvalidos,
    NaoEncontrado,
    nome_da_restricao,
)
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.eleitor_dto import EleitorResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import (
    CandidatoDaCedula,
    CargoDaCedula,
    CargoParticipacao,
    CedulaDoEleitor,
    Comparecimento,
    ComprovanteVoto,
    ContagemVoto,
    Escolha,
    Participacao,
    PedidoRegistro,
    PreviaVoto,
)
from app.models.enums import (
    DIGITOS_POR_CARGO,
    Cargo,
    ModoEscolha,
    StatusEleicao,
    TipoVoto,
    numero_valido_para_cargo,
)
from app.repositories.votacao_repository import VotacaoRepository
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService

PK_REGISTRO = "pk_registros_votacao"
# FK que dispara quando o eleitor é excluído no meio da confirmação (D-145).
FK_ELEITOR_DO_REGISTRO = "fk_registros_votacao_eleitor_id_eleitores"

MENSAGENS_DA_PREVIA = {
    TipoVoto.NOMINAL: "Confira os dados e confirme o voto.",
    TipoVoto.NULO: "Voto NULO: número sem candidato para este cargo.",
    TipoVoto.BRANCO: "Voto em BRANCO.",
}


def validar_pode_votar(eleicao: EleicaoResumo, agora: datetime) -> None:
    """RN-51 e RN-52: a eleição precisa estar ABERTA e dentro da janela de horário.

    Levanta 409 `ELEICAO_NAO_ABERTA` se o status não for ABERTA. Levanta 409 `JANELA_ENCERRADA`
    se hoje não é o dia da eleição ou o horário de encerramento já passou (o Chefe ainda não
    encerrou, mas o voto é recusado).
    """
    if eleicao.status != StatusEleicao.ABERTA:
        raise ConflitoDeEstado(
            "A eleição não está aberta.",
            codigo="ELEICAO_NAO_ABERTA",
            detalhes={"status": eleicao.status.value},
        )
    if agora.date() != eleicao.data or agora.time() >= eleicao.horario_encerramento:
        raise ConflitoDeEstado(
            "A janela de votação desta eleição já terminou.",
            codigo="JANELA_ENCERRADA",
            detalhes={"horario_encerramento": eleicao.horario_encerramento.isoformat()},
        )


def validar_eleitor_apto(eleitor_criado_em: datetime, eleicao_aberta_em: datetime) -> None:
    """RN-53: só vota quem foi cadastrado até o instante da abertura da eleição.

    Cadastrado no mesmo instante da abertura ainda é apto. Depois disso, 403 `ELEITOR_NAO_APTO`.
    """
    if eleitor_criado_em > eleicao_aberta_em:
        raise AcessoNegado(
            "Você foi cadastrado depois da abertura desta eleição e não pode votar nela.",
            codigo="ELEITOR_NAO_APTO",
        )


def resolver_escolha(
    cargo: Cargo,
    modo: ModoEscolha,
    numero: str | None,
    candidaturas_do_cargo: list[CandidaturaDetalhada],
) -> Escolha:
    """RN-58: transforma o que o eleitor digitou no tipo de voto que vale.

    - Modo BRANCO vira voto BRANCO (o número é ignorado).
    - Modo NUMERO exige a quantidade de dígitos do cargo; se faltar número ou ele for inválido,
      422 `NUMERO_INVALIDO_PARA_CARGO`.
    - Número que pertence a uma candidatura vira voto NOMINAL; número sem candidatura vira NULO.

    `candidaturas_do_cargo` são as candidaturas da eleição neste cargo.
    """
    if modo == ModoEscolha.BRANCO:
        return Escolha(TipoVoto.BRANCO)

    if numero is None or not numero_valido_para_cargo(numero, cargo):
        raise DadosInvalidos(
            f"O número deve ter {DIGITOS_POR_CARGO[cargo]} dígitos para {cargo.value}.",
            codigo="NUMERO_INVALIDO_PARA_CARGO",
            detalhes={"cargo": cargo.value, "digitos": DIGITOS_POR_CARGO[cargo]},
        )
    for candidatura in candidaturas_do_cargo:
        if candidatura.numero == numero:
            return Escolha(
                TipoVoto.NOMINAL,
                candidatura_id=candidatura.id,
                numero=candidatura.numero,
                nome_urna=candidatura.nome_urna,
                partido_sigla=candidatura.partido_sigla,
            )
    return Escolha(TipoVoto.NULO)


class VotacaoService:
    """Service de votação: casos de uso e transação.

    O voto tem duas etapas (RN-56): `registrar_voto` só confere e devolve uma prévia com a cédula
    assinada (nada é gravado, sem commit); `confirmar_voto` grava de forma definitiva, nas duas
    tabelas sem ligação entre si, na mesma transação (RN-60).
    """

    def __init__(
        self,
        sessao: Session,
        repository: VotacaoRepository | None = None,
        eleicoes: EleicaoService | None = None,
        eleitores: EleitorService | None = None,
    ) -> None:
        self.sessao = sessao
        self.repository = repository or VotacaoRepository(sessao)
        self.eleicoes = eleicoes or EleicaoService(sessao)
        self.eleitores = eleitores or EleitorService(sessao)

    def _eleitor_do(self, usuario: UsuarioAutenticado) -> EleitorResumo:
        """O eleitor desta credencial; 404 `ELEITOR_NAO_ENCONTRADO` se não houver."""
        eleitor = self.eleitores.obter_eleitor_do_usuario(usuario.id)
        if eleitor is None:
            raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
        return eleitor

    def _eleitor_apto_a_votar(
        self, usuario: UsuarioAutenticado, eleicao_id: int, agora: datetime
    ) -> tuple[EleitorResumo, EleicaoResumo]:
        """Passos comuns à cédula e ao registro: eleitor, eleição aberta na janela e eleitor apto.

        RN-51, RN-52 e RN-53. Devolve o eleitor e a eleição.
        """
        eleitor = self._eleitor_do(usuario)
        eleicao = self.eleicoes.obter_eleicao(eleicao_id)
        validar_pode_votar(eleicao, agora)
        validar_eleitor_apto(eleitor.criado_em, eleicao.aberta_em)
        return eleitor, eleicao

    def obter_cedula(
        self, usuario: UsuarioAutenticado, eleicao_id: int, agora: datetime
    ) -> CedulaDoEleitor:
        """Monta a cédula do eleitor: só os cargos disputados, na ordem da urna (RN-50 a 53, RN-55).

        Cada cargo informa os dígitos do número, os candidatos e se o eleitor já votou (RN-61).
        Não grava nada.
        """
        eleitor, _ = self._eleitor_apto_a_votar(usuario, eleicao_id, agora)
        candidaturas = self.eleicoes.listar_candidaturas(eleicao_id)
        votados = self.repository.cargos_votados(eleitor.id, eleicao_id)

        cargos = []
        for cargo in Cargo:  # a ordem do enum é a da urna
            do_cargo = [c for c in candidaturas if c.cargo == cargo]
            if not do_cargo:
                continue  # cargo sem candidatura não aparece (RN-55)
            cargos.append(
                CargoDaCedula(
                    cargo=cargo,
                    digitos=DIGITOS_POR_CARGO[cargo],
                    ja_votou=cargo in votados,
                    candidatos=[
                        CandidatoDaCedula(c.numero, c.nome_urna, c.partido_sigla) for c in do_cargo
                    ],
                )
            )
        return CedulaDoEleitor(eleicao_id=eleicao_id, cargos=cargos)

    def registrar_voto(
        self,
        usuario: UsuarioAutenticado,
        eleicao_id: int,
        pedido: PedidoRegistro,
        agora: datetime,
    ) -> PreviaVoto:
        """Etapa 1 do voto: confere tudo e devolve a prévia com a cédula assinada (RN-54 a 58).

        **Não grava nada e não faz commit** (RN-56): o eleitor pode registrar de novo para mudar
        de ideia. Ordem: eleitor e eleição (RN-50 a 53); já votou no cargo, 409
        `VOTO_JA_REGISTRADO` (RN-54); cargo sem candidaturas, 422 `CARGO_NAO_DISPUTADO` (RN-55);
        `resolver_escolha` (RN-58); cédula assinada, válida por 5 minutos (RN-57).
        """
        eleitor, _ = self._eleitor_apto_a_votar(usuario, eleicao_id, agora)
        if self.repository.ja_votou(eleitor.id, eleicao_id, pedido.cargo):
            raise ConflitoDeEstado("Você já votou para este cargo.", codigo="VOTO_JA_REGISTRADO")

        candidaturas = self.eleicoes.listar_candidaturas(eleicao_id, pedido.cargo)
        if not candidaturas:
            raise DadosInvalidos(
                "Este cargo não é disputado nesta eleição.",
                codigo="CARGO_NAO_DISPUTADO",
                detalhes={"cargo": pedido.cargo.value},
            )

        escolha = resolver_escolha(pedido.cargo, pedido.modo, pedido.numero, candidaturas)
        token, expira_em = emitir_cedula(usuario.id, eleicao_id, pedido.cargo, escolha, agora)
        candidato = None
        if escolha.tipo == TipoVoto.NOMINAL:
            candidato = CandidatoDaCedula(escolha.numero, escolha.nome_urna, escolha.partido_sigla)
        return PreviaVoto(
            eleicao_id=eleicao_id,
            cargo=pedido.cargo,
            tipo=escolha.tipo,
            candidato=candidato,
            mensagem=MENSAGENS_DA_PREVIA[escolha.tipo],
            token_cedula=token,
            expira_em=expira_em,
        )

    def confirmar_voto(
        self,
        usuario: UsuarioAutenticado,
        eleicao_id: int,
        token_cedula: str,
        agora: datetime,
    ) -> ComprovanteVoto:
        """Etapa 2: grava o voto de forma definitiva e faz commit (RN-54, RN-56, RN-59, RN-60).

        A cédula precisa ser do próprio eleitor e desta eleição (RN-57). A eleição é lida com
        trava compartilhada: o encerramento espera esta confirmação terminar (e vice-versa). As
        duas gravações (quem votou no cargo; o voto sem identificação) ficam na mesma transação,
        em tabelas sem ligação. Não há checagem de "já votou" antes: a chave primária decide de
        forma atômica e a violação vira 409 `VOTO_JA_REGISTRADO`. Eleitor excluído no meio da
        confirmação: a FK recusa e a resposta é 404 `ELEITOR_NAO_ENCONTRADO` (D-145). A resposta
        não contém a escolha.
        """
        cedula = ler_cedula(token_cedula, agora)
        if cedula.usuario_id != usuario.id or cedula.eleicao_id != eleicao_id:
            raise DadosInvalidos(
                "Esta cédula não pertence a você ou a esta eleição.", codigo="CEDULA_INVALIDA"
            )

        eleitor = self._eleitor_do(usuario)
        eleicao = self.eleicoes.obter_eleicao_para_votacao(eleicao_id)
        validar_pode_votar(eleicao, agora)
        validar_eleitor_apto(eleitor.criado_em, eleicao.aberta_em)

        try:
            self.repository.inserir_registro(eleitor.id, eleicao_id, cedula.cargo)
            self.repository.inserir_voto(
                eleicao_id, cedula.cargo, cedula.tipo, cedula.candidatura_id
            )
            self.sessao.commit()
        except IntegrityError as erro:
            self.sessao.rollback()
            if nome_da_restricao(erro) == PK_REGISTRO:
                raise ConflitoDeEstado(
                    "Você já votou para este cargo.", codigo="VOTO_JA_REGISTRADO"
                ) from erro
            if nome_da_restricao(erro) == FK_ELEITOR_DO_REGISTRO:
                raise NaoEncontrado(
                    "Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO"
                ) from erro
            raise

        return ComprovanteVoto(
            eleicao_id=eleicao_id, cargo=cedula.cargo, mensagem="Voto confirmado."
        )

    def obter_participacao(self, usuario: UsuarioAutenticado, eleicao_id: int) -> Participacao:
        """Lista os cargos disputados e se o eleitor já votou em cada um, sem escolha (RN-61).

        Vale em qualquer status da eleição. 404 se a eleição ou o eleitor não existirem.
        """
        eleitor = self._eleitor_do(usuario)
        candidaturas = self.eleicoes.listar_candidaturas(eleicao_id)
        votados = self.repository.cargos_votados(eleitor.id, eleicao_id)
        disputados = {c.cargo for c in candidaturas}
        return Participacao(
            eleicao_id=eleicao_id,
            cargos=[
                CargoParticipacao(cargo, cargo in votados) for cargo in Cargo if cargo in disputados
            ],
        )

    def contar_votos(self, eleicao_id: int) -> list[ContagemVoto]:
        """Contagem de votos por cargo, tipo e candidatura, para a apuração (RN-74)."""
        return self.repository.contar_votos(eleicao_id)

    def contar_comparecimento(self, eleicao_id: int) -> Comparecimento:
        """Eleitores que votaram em ao menos um cargo e votos registrados por cargo (RN-79)."""
        return self.repository.contar_comparecimento(eleicao_id)
