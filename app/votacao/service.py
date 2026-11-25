"""Service da votação: casos de uso e transação. Única porta de entrada do módulo.

O voto tem duas etapas (RN-56): `registrar_voto` só confere e devolve uma prévia com a cédula
assinada (nada é gravado, sem commit); `confirmar_voto` grava de forma definitiva, nas duas
tabelas sem ligação entre si, na mesma transação (RN-60).
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cedula import emitir_cedula, ler_cedula
from app.core.exceptions import (
    ConflitoDeEstado,
    DadosInvalidos,
    NaoEncontrado,
    nome_da_restricao,
)
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
    Participacao,
    PedidoRegistro,
    PreviaVoto,
)
from app.eleicoes import service as eleicoes_service
from app.models.enums import DIGITOS_POR_CARGO, Cargo, TipoVoto
from app.repositories.votacao_repository import VotacaoRepository
from app.services.eleitor_service import EleitorService
from app.votacao import dominio

PK_REGISTRO = "pk_registros_votacao"
# FK que dispara quando o eleitor é excluído no meio da confirmação (D-145).
FK_ELEITOR_DO_REGISTRO = "fk_registros_votacao_eleitor_id_eleitores"

MENSAGENS_DA_PREVIA = {
    TipoVoto.NOMINAL: "Confira os dados e confirme o voto.",
    TipoVoto.NULO: "Voto NULO: número sem candidato para este cargo.",
    TipoVoto.BRANCO: "Voto em BRANCO.",
}


def _eleitor_do(sessao: Session, usuario: UsuarioAutenticado) -> EleitorResumo:
    """O eleitor desta credencial; 404 `ELEITOR_NAO_ENCONTRADO` se não houver."""
    eleitor = EleitorService(sessao).obter_eleitor_do_usuario(usuario.id)
    if eleitor is None:
        raise NaoEncontrado("Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO")
    return eleitor


def _eleitor_apto_a_votar(
    sessao: Session, usuario: UsuarioAutenticado, eleicao_id: int, agora: datetime
) -> tuple[EleitorResumo, EleicaoResumo]:
    """Passos comuns à cédula e ao registro: eleitor, eleição aberta na janela e eleitor apto.

    RN-51, RN-52 e RN-53. Devolve o eleitor e a eleição.
    """
    eleitor = _eleitor_do(sessao, usuario)
    eleicao = eleicoes_service.obter_eleicao(sessao, eleicao_id)
    dominio.validar_pode_votar(eleicao, agora)
    dominio.validar_eleitor_apto(eleitor.criado_em, eleicao.aberta_em)
    return eleitor, eleicao


def obter_cedula(
    sessao: Session, usuario: UsuarioAutenticado, eleicao_id: int, agora: datetime
) -> CedulaDoEleitor:
    """Monta a cédula do eleitor: só os cargos disputados, na ordem da urna (RN-50 a 53, RN-55).

    Cada cargo informa os dígitos do número, os candidatos e se o eleitor já votou (RN-61).
    Não grava nada.
    """
    eleitor, _ = _eleitor_apto_a_votar(sessao, usuario, eleicao_id, agora)
    candidaturas = eleicoes_service.listar_candidaturas(sessao, eleicao_id)
    votados = VotacaoRepository(sessao).cargos_votados(eleitor.id, eleicao_id)

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
    sessao: Session,
    usuario: UsuarioAutenticado,
    eleicao_id: int,
    pedido: PedidoRegistro,
    agora: datetime,
) -> PreviaVoto:
    """Etapa 1 do voto: confere tudo e devolve a prévia com a cédula assinada (RN-54 a 58).

    **Não grava nada e não faz commit** (RN-56): o eleitor pode registrar de novo para mudar de
    ideia. Ordem: eleitor e eleição (RN-50 a 53); já votou no cargo, 409 `VOTO_JA_REGISTRADO`
    (RN-54); cargo sem candidaturas, 422 `CARGO_NAO_DISPUTADO` (RN-55); `resolver_escolha`
    (RN-58); cédula assinada, válida por 5 minutos (RN-57).
    """
    eleitor, _ = _eleitor_apto_a_votar(sessao, usuario, eleicao_id, agora)
    if VotacaoRepository(sessao).ja_votou(eleitor.id, eleicao_id, pedido.cargo):
        raise ConflitoDeEstado("Você já votou para este cargo.", codigo="VOTO_JA_REGISTRADO")

    candidaturas = eleicoes_service.listar_candidaturas(sessao, eleicao_id, pedido.cargo)
    if not candidaturas:
        raise DadosInvalidos(
            "Este cargo não é disputado nesta eleição.",
            codigo="CARGO_NAO_DISPUTADO",
            detalhes={"cargo": pedido.cargo.value},
        )

    escolha = dominio.resolver_escolha(pedido.cargo, pedido.modo, pedido.numero, candidaturas)
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
    sessao: Session,
    usuario: UsuarioAutenticado,
    eleicao_id: int,
    token_cedula: str,
    agora: datetime,
) -> ComprovanteVoto:
    """Etapa 2: grava o voto de forma definitiva e faz commit (RN-54, RN-56, RN-59, RN-60).

    A cédula precisa ser do próprio eleitor e desta eleição (RN-57). A eleição é lida com
    trava compartilhada: o encerramento espera esta confirmação terminar (e vice-versa). As duas
    gravações (quem votou no cargo; o voto sem identificação) ficam na mesma transação, em
    tabelas sem ligação. Não há checagem de "já votou" antes: a chave primária decide de forma
    atômica e a violação vira 409 `VOTO_JA_REGISTRADO`. Eleitor excluído no meio da confirmação:
    a FK recusa e a resposta é 404 `ELEITOR_NAO_ENCONTRADO` (D-145). A resposta não contém a
    escolha.
    """
    cedula = ler_cedula(token_cedula, agora)
    if cedula.usuario_id != usuario.id or cedula.eleicao_id != eleicao_id:
        raise DadosInvalidos(
            "Esta cédula não pertence a você ou a esta eleição.", codigo="CEDULA_INVALIDA"
        )

    eleitor = _eleitor_do(sessao, usuario)
    eleicao = eleicoes_service.obter_eleicao_para_votacao(sessao, eleicao_id)
    dominio.validar_pode_votar(eleicao, agora)
    dominio.validar_eleitor_apto(eleitor.criado_em, eleicao.aberta_em)

    try:
        VotacaoRepository(sessao).inserir_registro(eleitor.id, eleicao_id, cedula.cargo)
        VotacaoRepository(sessao).inserir_voto(
            eleicao_id, cedula.cargo, cedula.tipo, cedula.candidatura_id
        )
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        if nome_da_restricao(erro) == PK_REGISTRO:
            raise ConflitoDeEstado(
                "Você já votou para este cargo.", codigo="VOTO_JA_REGISTRADO"
            ) from erro
        if nome_da_restricao(erro) == FK_ELEITOR_DO_REGISTRO:
            raise NaoEncontrado(
                "Eleitor não encontrado.", codigo="ELEITOR_NAO_ENCONTRADO"
            ) from erro
        raise

    return ComprovanteVoto(eleicao_id=eleicao_id, cargo=cedula.cargo, mensagem="Voto confirmado.")


def obter_participacao(
    sessao: Session, usuario: UsuarioAutenticado, eleicao_id: int
) -> Participacao:
    """Lista os cargos disputados e se o eleitor já votou em cada um, sem escolha (RN-61).

    Vale em qualquer status da eleição. 404 se a eleição ou o eleitor não existirem.
    """
    eleitor = _eleitor_do(sessao, usuario)
    candidaturas = eleicoes_service.listar_candidaturas(sessao, eleicao_id)
    votados = VotacaoRepository(sessao).cargos_votados(eleitor.id, eleicao_id)
    disputados = {c.cargo for c in candidaturas}
    return Participacao(
        eleicao_id=eleicao_id,
        cargos=[
            CargoParticipacao(cargo, cargo in votados) for cargo in Cargo if cargo in disputados
        ],
    )


def contar_votos(sessao: Session, eleicao_id: int) -> list[ContagemVoto]:
    """Contagem de votos por cargo, tipo e candidatura, para a apuração (RN-74)."""
    return VotacaoRepository(sessao).contar_votos(eleicao_id)


def contar_comparecimento(sessao: Session, eleicao_id: int) -> Comparecimento:
    """Eleitores que votaram em ao menos um cargo e votos registrados por cargo (RN-79)."""
    return VotacaoRepository(sessao).contar_comparecimento(eleicao_id)
