"""Casos de uso de eleições. É a única porta de entrada do módulo para os outros.

A eleição é a raiz do agregado: toda alteração começa travando a linha dela com
`SELECT ... FOR UPDATE`. As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.candidatos import servico as servico_candidatos
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import ConflitoDeEstado, DadosInvalidos, NaoEncontrado
from app.eleicoes import repositorio
from app.eleicoes.dominio import (
    AlteracoesCandidatura,
    AlteracoesEleicao,
    CandidaturaDetalhada,
    EleicaoResumo,
    NovaCandidaturaDados,
    NovaEleicaoDados,
    StatusEleicao,
    validar_abertura,
    validar_agendamento,
    validar_candidatura,
    validar_edicao,
    validar_encerramento,
)
from app.eleicoes.modelos import Candidatura, Eleicao


def _resumir(eleicao: Eleicao) -> EleicaoResumo:
    """Converte o modelo no resumo do domínio. O ORM não sai do módulo."""
    return EleicaoResumo(
        id=eleicao.id,
        descricao=eleicao.descricao,
        data=eleicao.data,
        turno=eleicao.turno,
        horario_abertura=eleicao.horario_abertura,
        horario_encerramento=eleicao.horario_encerramento,
        status=StatusEleicao(eleicao.status),
        aberta_em=eleicao.aberta_em,
        encerrada_em=eleicao.encerrada_em,
        criado_em=eleicao.criado_em,
    )


def _ou_nao_encontrada(eleicao: Eleicao | None) -> Eleicao:
    """Devolve a eleição ou levanta 404 `ELEICAO_NAO_ENCONTRADA`."""
    if eleicao is None:
        raise NaoEncontrado("Eleição não encontrada.", codigo="ELEICAO_NAO_ENCONTRADA")
    return eleicao


def _conferir_data_e_turno_livres(
    sessao: Session, dados: NovaEleicaoDados, ignorando_id: int | None = None
) -> None:
    """RN-12: levanta 409 `ELEICAO_DUPLICADA` se outra eleição já usa esta data e turno."""
    if repositorio.existe_eleicao_na_data_e_turno(sessao, dados.data, dados.turno, ignorando_id):
        raise ConflitoDeEstado(
            "Já existe uma eleição nesta data e turno.", codigo="ELEICAO_DUPLICADA"
        )


def criar_eleicao(sessao: Session, dados: NovaEleicaoDados, agora: datetime) -> EleicaoResumo:
    """Agenda uma eleição (status AGENDADA) e faz commit (RN-10, RN-11, RN-12).

    RN-11: turno 1 ou 2, abertura antes do encerramento e data não anterior a hoje (422).
    RN-12: já existir eleição na mesma data e turno dá 409 `ELEICAO_DUPLICADA`.
    """
    dados = validar_agendamento(dados, hoje=agora.date())
    _conferir_data_e_turno_livres(sessao, dados)
    eleicao = Eleicao(
        descricao=dados.descricao,
        data=dados.data,
        turno=dados.turno,
        horario_abertura=dados.horario_abertura,
        horario_encerramento=dados.horario_encerramento,
        status=StatusEleicao.AGENDADA.value,
        criado_em=agora,
    )
    repositorio.inserir(sessao, eleicao)
    sessao.commit()
    return _resumir(eleicao)


def editar_eleicao(
    sessao: Session, eleicao_id: int, alteracoes: AlteracoesEleicao, agora: datetime
) -> EleicaoResumo:
    """Altera descrição, data, turno e/ou horários de uma eleição AGENDADA e faz commit.

    Trava a eleição; RN-14: só AGENDADA pode mudar (`ELEICAO_NAO_EDITAVEL`, 409). Os dados
    resultantes passam de novo pela RN-11 e pela RN-12 (ignorando a própria eleição).
    Eleição inexistente: 404 `ELEICAO_NAO_ENCONTRADA`.
    """
    eleicao = _ou_nao_encontrada(repositorio.obter_com_trava_exclusiva(sessao, eleicao_id))
    validar_edicao(StatusEleicao(eleicao.status))
    dados = validar_agendamento(
        NovaEleicaoDados(
            descricao=_ou(alteracoes.descricao, eleicao.descricao),
            data=_ou(alteracoes.data, eleicao.data),
            turno=_ou(alteracoes.turno, eleicao.turno),
            horario_abertura=_ou(alteracoes.horario_abertura, eleicao.horario_abertura),
            horario_encerramento=_ou(alteracoes.horario_encerramento, eleicao.horario_encerramento),
        ),
        hoje=agora.date(),
    )
    _conferir_data_e_turno_livres(sessao, dados, ignorando_id=eleicao.id)
    eleicao.descricao = dados.descricao
    eleicao.data = dados.data
    eleicao.turno = dados.turno
    eleicao.horario_abertura = dados.horario_abertura
    eleicao.horario_encerramento = dados.horario_encerramento
    sessao.commit()
    return _resumir(eleicao)


def _ou[T](novo: T | None, atual: T) -> T:
    """O valor novo, se veio; senão o atual (campo `None` significa "não alterar")."""
    return atual if novo is None else novo


def obter_eleicao(sessao: Session, eleicao_id: int) -> EleicaoResumo:
    """Consulta uma eleição (RN-19). Levanta 404 `ELEICAO_NAO_ENCONTRADA` se não existir."""
    return _resumir(_ou_nao_encontrada(repositorio.buscar_por_id(sessao, eleicao_id)))


def listar_eleicoes(sessao: Session, status: StatusEleicao | None = None) -> list[EleicaoResumo]:
    """Lista as eleições, da mais antiga para a mais nova, com filtro opcional de status (RN-19)."""
    return [_resumir(eleicao) for eleicao in repositorio.listar(sessao, status)]


def abrir_eleicao(sessao: Session, eleicao_id: int, agora: datetime) -> EleicaoResumo:
    """Abre a votação (AGENDADA → ABERTA), registra `aberta_em` e faz commit (RN-13, RN-15 a 17).

    Trava a eleição e confere, nesta ordem (`validar_abertura`): status, nenhuma outra aberta,
    data, janela, ao menos uma candidatura e, no 2º turno, 2 por cargo. Se duas aberturas
    simultâneas passarem pelas conferências, o índice parcial do banco recusa a segunda
    (409 `OUTRA_ELEICAO_ABERTA`, traduzido pelo tratador de `IntegrityError`).
    Eleição inexistente: 404 `ELEICAO_NAO_ENCONTRADA`.
    """
    eleicao = _ou_nao_encontrada(repositorio.obter_com_trava_exclusiva(sessao, eleicao_id))
    validar_abertura(
        _resumir(eleicao),
        agora,
        existe_outra_aberta=repositorio.existe_eleicao_aberta(sessao),
        candidaturas_por_cargo=repositorio.contar_candidaturas_por_cargo(sessao, eleicao.id),
    )
    eleicao.status = StatusEleicao.ABERTA.value
    eleicao.aberta_em = agora
    sessao.commit()
    return _resumir(eleicao)


def encerrar_eleicao(sessao: Session, eleicao_id: int, agora: datetime) -> EleicaoResumo:
    """Encerra a votação (ABERTA → ENCERRADA), registra `encerrada_em` e faz commit (RN-18).

    Pode ser feito a qualquer hora, antes ou depois do horário previsto. A trava exclusiva
    espera as confirmações de voto em andamento (que seguram a trava compartilhada) terminarem:
    depois disso, nenhum voto novo entra. Levanta 409 `TRANSICAO_INVALIDA` se não estiver ABERTA
    e 404 `ELEICAO_NAO_ENCONTRADA` se não existir.
    """
    eleicao = _ou_nao_encontrada(repositorio.obter_com_trava_exclusiva(sessao, eleicao_id))
    validar_encerramento(StatusEleicao(eleicao.status))
    eleicao.status = StatusEleicao.ENCERRADA.value
    eleicao.encerrada_em = agora
    sessao.commit()
    return _resumir(eleicao)


def obter_eleicao_para_votacao(sessao: Session, eleicao_id: int) -> EleicaoResumo:
    """Consulta a eleição com `SELECT ... FOR SHARE` para o módulo de votação.

    A trava compartilhada dura até o fim da transação de quem chama e impede `encerrar_eleicao`
    de passar no meio de uma confirmação de voto. **Não faz commit**: quem chama controla a
    transação. Levanta 404 `ELEICAO_NAO_ENCONTRADA` se não existir.
    """
    return _resumir(
        _ou_nao_encontrada(repositorio.obter_com_trava_compartilhada(sessao, eleicao_id))
    )


# ---------------------------------------------------------------- candidaturas


def _eleicao_editavel(sessao: Session, eleicao_id: int) -> Eleicao:
    """Trava a eleição (raiz do agregado) e confere que está AGENDADA (RN-40).

    404 `ELEICAO_NAO_ENCONTRADA` se não existir; 409 `ELEICAO_NAO_EDITAVEL` se não for AGENDADA.
    """
    eleicao = _ou_nao_encontrada(repositorio.obter_com_trava_exclusiva(sessao, eleicao_id))
    validar_edicao(StatusEleicao(eleicao.status))
    return eleicao


def _conferir_partido(sessao: Session, partido_id: int) -> None:
    """RN-46: levanta 422 `REFERENCIA_INEXISTENTE` (`detalhes.campo` = `partido_id`)."""
    if servico_candidatos.obter_partido(sessao, partido_id) is None:
        raise DadosInvalidos(
            "O partido informado não existe.",
            codigo="REFERENCIA_INEXISTENTE",
            detalhes={"campo": "partido_id"},
        )


def _conferir_candidato(sessao: Session, candidato_id: int) -> None:
    """RN-46: levanta 422 `REFERENCIA_INEXISTENTE` (`detalhes.campo` = `candidato_id`)."""
    if not servico_candidatos.obter_resumos_de_candidatos(sessao, [candidato_id]):
        raise DadosInvalidos(
            "O candidato informado não existe.",
            codigo="REFERENCIA_INEXISTENTE",
            detalhes={"campo": "candidato_id"},
        )


def _conferir_regras_da_candidatura(
    sessao: Session,
    eleicao: Eleicao,
    cargo: Cargo,
    numero: str,
    ignorando_id: int | None = None,
) -> None:
    """RN-42, RN-45 e RN-43, nesta ordem. `ignorando_id` é a candidatura em edição."""
    quantidade = repositorio.contar_candidaturas_no_cargo(sessao, eleicao.id, cargo, ignorando_id)
    validar_candidatura(_resumir(eleicao), cargo, numero, quantidade)
    _conferir_numero_livre(sessao, eleicao.id, cargo, numero, ignorando_id)


def _conferir_numero_livre(
    sessao: Session, eleicao_id: int, cargo: Cargo, numero: str, ignorando_id: int | None = None
) -> None:
    """RN-43: levanta 409 `NUMERO_JA_UTILIZADO` se outra candidatura usa o número no cargo."""
    if repositorio.existe_numero_no_cargo(sessao, eleicao_id, cargo, numero, ignorando_id):
        raise ConflitoDeEstado(
            "Este número já é usado por outra candidatura neste cargo.",
            codigo="NUMERO_JA_UTILIZADO",
        )


def _detalhar(sessao: Session, candidaturas: list[Candidatura]) -> list[CandidaturaDetalhada]:
    """Junta, em memória, os dados de exibição do candidato e do partido de cada candidatura.

    Ordena pela ordem do enum `Cargo` e depois pelo número (seção 9.5).
    """
    candidatos = servico_candidatos.obter_resumos_de_candidatos(
        sessao, [c.candidato_id for c in candidaturas]
    )
    partidos = {partido.id: partido for partido in servico_candidatos.listar_partidos(sessao)}
    ordem_dos_cargos = list(Cargo)
    detalhadas = [
        CandidaturaDetalhada(
            id=c.id,
            eleicao_id=c.eleicao_id,
            cargo=Cargo(c.cargo),
            numero=c.numero,
            candidato_id=c.candidato_id,
            nome_urna=candidatos[c.candidato_id].nome_urna,
            data_nascimento=candidatos[c.candidato_id].data_nascimento,
            partido_id=c.partido_id,
            partido_sigla=partidos[c.partido_id].sigla,
            partido_numero=partidos[c.partido_id].numero,
        )
        for c in candidaturas
    ]
    return sorted(detalhadas, key=lambda d: (ordem_dos_cargos.index(d.cargo), d.numero))


def criar_candidatura(
    sessao: Session, eleicao_id: int, dados: NovaCandidaturaDados, agora: datetime
) -> CandidaturaDetalhada:
    """Cria uma candidatura pela raiz do agregado e faz commit (RN-40 a RN-46).

    Trava a eleição; só AGENDADA (RN-40). Candidato e partido precisam existir (RN-46, 422).
    Número com os dígitos do cargo (RN-42) e, no 2º turno, só Governador e Presidente com no
    máximo 2 candidaturas por cargo (RN-45), via `validar_candidatura`.
    Número já usado no cargo → 409 `NUMERO_JA_UTILIZADO` (RN-43); candidato que já tem
    candidatura na eleição → 409 `CANDIDATURA_DUPLICADA` (RN-44).
    """
    eleicao = _eleicao_editavel(sessao, eleicao_id)
    _conferir_candidato(sessao, dados.candidato_id)
    _conferir_partido(sessao, dados.partido_id)
    _conferir_regras_da_candidatura(sessao, eleicao, dados.cargo, dados.numero)
    if repositorio.existe_candidatura_do_candidato(sessao, eleicao.id, dados.candidato_id):
        raise ConflitoDeEstado(
            "Este candidato já tem candidatura nesta eleição.", codigo="CANDIDATURA_DUPLICADA"
        )
    candidatura = Candidatura(
        eleicao_id=eleicao.id,
        candidato_id=dados.candidato_id,
        partido_id=dados.partido_id,
        cargo=dados.cargo.value,
        numero=dados.numero,
        criado_em=agora,
    )
    repositorio.inserir_candidatura(sessao, candidatura)
    sessao.commit()
    return _detalhar(sessao, [candidatura])[0]


def editar_candidatura(
    sessao: Session, eleicao_id: int, candidatura_id: int, alteracoes: AlteracoesCandidatura
) -> CandidaturaDetalhada:
    """Altera cargo, número e/ou partido (nunca candidato ou eleição) e faz commit (RN-40).

    Mesma trava e mesmas regras da criação, ignorando a própria candidatura nas conferências
    de duplicidade. Candidatura inexistente na eleição: 404 `CANDIDATURA_NAO_ENCONTRADA`.
    """
    eleicao = _eleicao_editavel(sessao, eleicao_id)
    candidatura = _candidatura_ou_nao_encontrada(sessao, eleicao.id, candidatura_id)
    cargo = _ou(alteracoes.cargo, Cargo(candidatura.cargo))
    numero = _ou(alteracoes.numero, candidatura.numero)
    partido_id = _ou(alteracoes.partido_id, candidatura.partido_id)
    _conferir_partido(sessao, partido_id)
    _conferir_regras_da_candidatura(sessao, eleicao, cargo, numero, ignorando_id=candidatura.id)
    candidatura.cargo = cargo.value
    candidatura.numero = numero
    candidatura.partido_id = partido_id
    sessao.commit()
    return _detalhar(sessao, [candidatura])[0]


def _candidatura_ou_nao_encontrada(
    sessao: Session, eleicao_id: int, candidatura_id: int
) -> Candidatura:
    """Devolve a candidatura da eleição ou levanta 404 `CANDIDATURA_NAO_ENCONTRADA`."""
    candidatura = repositorio.buscar_candidatura(sessao, eleicao_id, candidatura_id)
    if candidatura is None:
        raise NaoEncontrado("Candidatura não encontrada.", codigo="CANDIDATURA_NAO_ENCONTRADA")
    return candidatura


def remover_candidatura(sessao: Session, eleicao_id: int, candidatura_id: int) -> None:
    """Remove a candidatura (só com a eleição AGENDADA, RN-40) e faz commit.

    404 `CANDIDATURA_NAO_ENCONTRADA` se ela não existir nesta eleição.
    """
    eleicao = _eleicao_editavel(sessao, eleicao_id)
    candidatura = _candidatura_ou_nao_encontrada(sessao, eleicao.id, candidatura_id)
    repositorio.remover_candidatura(sessao, candidatura)
    sessao.commit()


def listar_candidaturas(
    sessao: Session, eleicao_id: int, cargo: Cargo | None = None
) -> list[CandidaturaDetalhada]:
    """Candidaturas da eleição, ordenadas pelo enum `Cargo` e depois pelo número (RN-40).

    `cargo` filtra. 404 `ELEICAO_NAO_ENCONTRADA` se a eleição não existir.
    """
    _ou_nao_encontrada(repositorio.buscar_por_id(sessao, eleicao_id))
    return _detalhar(sessao, repositorio.listar_candidaturas(sessao, eleicao_id, cargo))


def candidaturas_do_usuario(sessao: Session, usuario_id: int) -> list[CandidaturaDetalhada]:
    """As candidaturas do candidato logado, em todas as eleições (RN-47).

    Ordenadas por eleição, cargo e número. Credencial sem candidato (por exemplo, um eleitor)
    devolve lista vazia; quem barra o acesso é a rota (só o perfil CANDIDATO).
    """
    candidato = servico_candidatos.obter_candidato_do_usuario(sessao, usuario_id)
    if candidato is None:
        return []
    candidaturas = _detalhar(
        sessao, repositorio.listar_candidaturas_do_candidato(sessao, candidato.id)
    )
    return sorted(candidaturas, key=lambda c: c.eleicao_id)


def buscar_candidatura_por_numero(
    sessao: Session, eleicao_id: int, cargo: Cargo, numero: str
) -> CandidaturaDetalhada | None:
    """A candidatura que usa este número neste cargo da eleição, ou `None`.

    Usada pela votação para decidir entre voto NOMINAL (existe) e NULO (não existe).
    """
    candidatura = repositorio.buscar_candidatura_por_numero(sessao, eleicao_id, cargo, numero)
    return _detalhar(sessao, [candidatura])[0] if candidatura else None
