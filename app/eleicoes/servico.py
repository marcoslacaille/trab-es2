"""Casos de uso de eleições. É a única porta de entrada do módulo para os outros.

A eleição é a raiz do agregado: toda alteração começa travando a linha dela com
`SELECT ... FOR UPDATE`. As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.compartilhado.erros import ConflitoDeEstado, NaoEncontrado
from app.eleicoes import repositorio
from app.eleicoes.dominio import (
    AlteracoesEleicao,
    EleicaoResumo,
    NovaEleicaoDados,
    StatusEleicao,
    validar_abertura,
    validar_agendamento,
    validar_edicao,
    validar_encerramento,
)
from app.eleicoes.modelos import Eleicao


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
