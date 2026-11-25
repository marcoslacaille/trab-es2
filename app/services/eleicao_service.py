"""Service de eleições e candidaturas: casos de uso, regras do ciclo de vida e transação.

A eleição é a raiz do agregado: toda alteração começa travando a linha dela (`FOR UPDATE`).
"""

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflitoDeEstado,
    DadosInvalidos,
    NaoEncontrado,
    nome_da_restricao,
)
from app.dto.candidatura_dto import (
    AlteracoesCandidatura,
    CandidaturaDetalhada,
    NovaCandidaturaDados,
)
from app.dto.eleicao_dto import AlteracoesEleicao, EleicaoResumo, NovaEleicaoDados
from app.models.candidatura import Candidatura
from app.models.eleicao import Eleicao
from app.models.enums import (
    CARGOS_DO_SEGUNDO_TURNO,
    DIGITOS_POR_CARGO,
    Cargo,
    StatusEleicao,
    numero_valido_para_cargo,
)
from app.repositories.eleicao_repository import EleicaoRepository
from app.services.candidato_service import CandidatoService
from app.services.partido_service import PartidoService

DESCRICAO_MAXIMA = 120
CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO = 2

# FK que dispara quando o candidato some entre a conferência e a gravação.
FK_CANDIDATO_DA_CANDIDATURA = "fk_candidaturas_candidato_id_candidatos"


def validar_agendamento(dados: NovaEleicaoDados, hoje: date) -> NovaEleicaoDados:
    """RN-11: confere os dados de uma eleição ao criá-la ou editá-la e os devolve normalizados.

    A descrição, sem os espaços das pontas, tem de 1 a 120 caracteres; o turno é 1 ou 2; o
    horário de abertura vem antes do de encerramento; a data não é anterior a `hoje`.
    Levanta `DadosInvalidos` com `DADOS_INVALIDOS`, `JANELA_INVALIDA` ou `DATA_NO_PASSADO` (422).
    """
    descricao = dados.descricao.strip()
    if not 1 <= len(descricao) <= DESCRICAO_MAXIMA:
        raise DadosInvalidos(
            f"A descrição deve ter de 1 a {DESCRICAO_MAXIMA} caracteres.", codigo="DADOS_INVALIDOS"
        )
    if dados.turno not in (1, 2):
        raise DadosInvalidos("O turno deve ser 1 ou 2.", codigo="DADOS_INVALIDOS")
    if dados.horario_abertura >= dados.horario_encerramento:
        raise DadosInvalidos(
            "O horário de abertura deve ser anterior ao de encerramento.",
            codigo="JANELA_INVALIDA",
        )
    if dados.data < hoje:
        raise DadosInvalidos(
            "A data da eleição não pode ser anterior a hoje.", codigo="DATA_NO_PASSADO"
        )
    return NovaEleicaoDados(
        descricao=descricao,
        data=dados.data,
        turno=dados.turno,
        horario_abertura=dados.horario_abertura,
        horario_encerramento=dados.horario_encerramento,
    )


def validar_edicao(status: StatusEleicao) -> None:
    """RN-14: descrição, data, turno e horários só mudam enquanto a eleição está AGENDADA.

    Também vale para criar, alterar e remover candidaturas (RN-40).
    Levanta `ConflitoDeEstado` com `ELEICAO_NAO_EDITAVEL` (409).
    """
    if status != StatusEleicao.AGENDADA:
        raise ConflitoDeEstado(
            "Só uma eleição AGENDADA pode ser alterada.",
            codigo="ELEICAO_NAO_EDITAVEL",
            detalhes={"status": status.value},
        )


def _validar_segundo_turno_completo(candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-17: no 2º turno, cada cargo com candidatura tem exatamente 2 (409 se não)."""
    incompletos = [
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade != CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO
    ]
    if incompletos:
        raise ConflitoDeEstado(
            "No 2º turno, cada cargo disputado precisa ter exatamente 2 candidaturas.",
            codigo="SEGUNDO_TURNO_INCOMPLETO",
            detalhes={"cargos": sorted(incompletos)},
        )


def _validar_cargos_do_segundo_turno(candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-45: no 2º turno só há candidaturas de Governador e Presidente (409 se não)."""
    proibidos = sorted(
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade > 0 and cargo not in CARGOS_DO_SEGUNDO_TURNO
    )
    if proibidos:
        raise ConflitoDeEstado(
            "No 2º turno só há Governador e Presidente.",
            codigo="CARGO_NAO_PERMITIDO_NO_TURNO",
            detalhes={"cargos": proibidos},
        )


def validar_candidaturas_no_turno(turno: int, candidaturas_por_cargo: dict[Cargo, int]) -> None:
    """RN-45: as candidaturas já cadastradas cabem no turno? Usada ao editar a eleição.

    Sem isto, trocar o turno de 1 para 2 deixaria um 2º turno com Senador ou com 3 candidatos a
    Presidente. No 1º turno não há restrição. No 2º, confere nesta ordem: só Governador e
    Presidente (`CARGO_NAO_PERMITIDO_NO_TURNO`, 409) e no máximo 2 por cargo
    (`LIMITE_SEGUNDO_TURNO`, 409); `detalhes.cargos` lista os cargos com problema.
    """
    if turno != 2:
        return
    _validar_cargos_do_segundo_turno(candidaturas_por_cargo)
    excedentes = sorted(
        cargo.value
        for cargo, quantidade in candidaturas_por_cargo.items()
        if quantidade > CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO
    )
    if excedentes:
        raise ConflitoDeEstado(
            f"No 2º turno cada cargo tem no máximo {CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO} "
            "candidaturas.",
            codigo="LIMITE_SEGUNDO_TURNO",
            detalhes={"cargos": excedentes},
        )


def validar_abertura(
    eleicao: EleicaoResumo,
    agora: datetime,
    existe_outra_aberta: bool,
    candidaturas_por_cargo: dict[Cargo, int],
) -> None:
    """RN-13, RN-15, RN-16, RN-17 e RN-45: confere se a eleição pode ser aberta agora.

    Confere nesta ordem, e a primeira falha é a devolvida (todas são 409): status AGENDADA
    (`TRANSICAO_INVALIDA`); nenhuma outra eleição aberta (`OUTRA_ELEICAO_ABERTA`); hoje é a data
    da eleição (`FORA_DA_DATA`); horário entre a abertura (inclusive) e o encerramento
    (exclusive) (`FORA_DA_JANELA`); ao menos uma candidatura (`SEM_CANDIDATURAS`); no 2º turno,
    só Governador e Presidente (`CARGO_NAO_PERMITIDO_NO_TURNO`, segunda barreira da RN-45) e
    exatamente 2 candidaturas em cada cargo disputado (`SEGUNDO_TURNO_INCOMPLETO`).
    `candidaturas_por_cargo` só traz os cargos que têm candidatura.
    """
    if eleicao.status != StatusEleicao.AGENDADA:
        raise ConflitoDeEstado(
            "Só uma eleição AGENDADA pode ser aberta.",
            codigo="TRANSICAO_INVALIDA",
            detalhes={"status": eleicao.status.value},
        )
    if existe_outra_aberta:
        raise ConflitoDeEstado("Já existe outra eleição aberta.", codigo="OUTRA_ELEICAO_ABERTA")
    if agora.date() != eleicao.data:
        raise ConflitoDeEstado(
            "A eleição só pode ser aberta no dia dela.",
            codigo="FORA_DA_DATA",
            detalhes={"data_da_eleicao": eleicao.data.isoformat()},
        )
    if not eleicao.horario_abertura <= agora.time() < eleicao.horario_encerramento:
        raise ConflitoDeEstado(
            "A eleição só pode ser aberta dentro da janela de votação.",
            codigo="FORA_DA_JANELA",
            detalhes={
                "horario_abertura": eleicao.horario_abertura.isoformat(),
                "horario_encerramento": eleicao.horario_encerramento.isoformat(),
            },
        )
    if sum(candidaturas_por_cargo.values()) == 0:
        raise ConflitoDeEstado(
            "A eleição precisa de pelo menos uma candidatura para ser aberta.",
            codigo="SEM_CANDIDATURAS",
        )
    if eleicao.turno == 2:
        _validar_cargos_do_segundo_turno(candidaturas_por_cargo)
        _validar_segundo_turno_completo(candidaturas_por_cargo)


def validar_candidatura(
    eleicao: EleicaoResumo, cargo: Cargo, numero: str, quantidade_no_cargo: int
) -> None:
    """RN-42 e RN-45: confere o número e, no 2º turno, o cargo e o limite de candidaturas.

    `quantidade_no_cargo` é quantas candidaturas o cargo já tem na eleição, sem contar a que
    está sendo editada. Confere nesta ordem: número com os dígitos do cargo e sem zero à
    esquerda (`NUMERO_INVALIDO_PARA_CARGO`, 422); no 2º turno, só Governador e Presidente
    (`CARGO_NAO_PERMITIDO_NO_TURNO`, 409) e no máximo 2 por cargo (`LIMITE_SEGUNDO_TURNO`, 409).
    """
    if not numero_valido_para_cargo(numero, cargo):
        raise DadosInvalidos(
            f"O número {numero!r} não tem os dígitos do cargo {cargo.value}.",
            codigo="NUMERO_INVALIDO_PARA_CARGO",
            detalhes={"cargo": cargo.value, "digitos": DIGITOS_POR_CARGO[cargo]},
        )
    if eleicao.turno != 2:
        return
    if cargo not in CARGOS_DO_SEGUNDO_TURNO:
        raise ConflitoDeEstado(
            "No 2º turno só há Governador e Presidente.",
            codigo="CARGO_NAO_PERMITIDO_NO_TURNO",
            detalhes={"cargo": cargo.value},
        )
    if quantidade_no_cargo >= CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO:
        raise ConflitoDeEstado(
            f"No 2º turno cada cargo tem no máximo {CANDIDATURAS_DO_SEGUNDO_TURNO_POR_CARGO} "
            "candidaturas.",
            codigo="LIMITE_SEGUNDO_TURNO",
            detalhes={"cargo": cargo.value},
        )


def validar_encerramento(status: StatusEleicao) -> None:
    """RN-13 e RN-18: só se encerra uma eleição ABERTA, a qualquer hora.

    Levanta `ConflitoDeEstado` com `TRANSICAO_INVALIDA` (409).
    """
    if status != StatusEleicao.ABERTA:
        raise ConflitoDeEstado(
            "Só uma eleição ABERTA pode ser encerrada.",
            codigo="TRANSICAO_INVALIDA",
            detalhes={"status": status.value},
        )


class EleicaoService:
    """Service de eleições e candidaturas: casos de uso e transação.

    Os métodos chamados pelas rotas fazem `commit` no final.
    """

    def __init__(
        self,
        sessao: Session,
        repository: EleicaoRepository | None = None,
        candidatos: CandidatoService | None = None,
        partidos: PartidoService | None = None,
    ) -> None:
        self.sessao = sessao
        self.repository = repository or EleicaoRepository(sessao)
        self.candidatos = candidatos or CandidatoService(sessao)
        self.partidos = partidos or PartidoService(sessao)

    @staticmethod
    def _resumir(eleicao: Eleicao) -> EleicaoResumo:
        """Converte o modelo no resumo do domínio. O ORM não sai do service."""
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

    @staticmethod
    def _ou_nao_encontrada(eleicao: Eleicao | None) -> Eleicao:
        """Devolve a eleição ou levanta 404 `ELEICAO_NAO_ENCONTRADA`."""
        if eleicao is None:
            raise NaoEncontrado("Eleição não encontrada.", codigo="ELEICAO_NAO_ENCONTRADA")
        return eleicao

    @staticmethod
    def _ou[T](novo: T | None, atual: T) -> T:
        """O valor novo, se veio; senão o atual (campo `None` significa "não alterar")."""
        return atual if novo is None else novo

    def _conferir_data_e_turno_livres(
        self, dados: NovaEleicaoDados, ignorando_id: int | None = None
    ) -> None:
        """RN-12: levanta 409 `ELEICAO_DUPLICADA` se outra eleição já usa esta data e turno."""
        if self.repository.existe_eleicao_na_data_e_turno(dados.data, dados.turno, ignorando_id):
            raise ConflitoDeEstado(
                "Já existe uma eleição nesta data e turno.", codigo="ELEICAO_DUPLICADA"
            )

    def criar_eleicao(self, dados: NovaEleicaoDados, agora: datetime) -> EleicaoResumo:
        """Agenda uma eleição (status AGENDADA) e faz commit (RN-10, RN-11, RN-12).

        RN-11: turno 1 ou 2, abertura antes do encerramento e data não anterior a hoje (422).
        RN-12: já existir eleição na mesma data e turno dá 409 `ELEICAO_DUPLICADA`.
        """
        dados = validar_agendamento(dados, hoje=agora.date())
        self._conferir_data_e_turno_livres(dados)
        eleicao = Eleicao(
            descricao=dados.descricao,
            data=dados.data,
            turno=dados.turno,
            horario_abertura=dados.horario_abertura,
            horario_encerramento=dados.horario_encerramento,
            status=StatusEleicao.AGENDADA.value,
            criado_em=agora,
        )
        self.repository.inserir(eleicao)
        self.sessao.commit()
        return self._resumir(eleicao)

    def editar_eleicao(
        self, eleicao_id: int, alteracoes: AlteracoesEleicao, agora: datetime
    ) -> EleicaoResumo:
        """Altera descrição, data, turno e/ou horários de uma eleição AGENDADA e faz commit.

        Trava a eleição; RN-14: só AGENDADA pode mudar (`ELEICAO_NAO_EDITAVEL`, 409). Os dados
        resultantes passam de novo pela RN-11 e pela RN-12 (ignorando a própria eleição) e, se a
        eleição for de 2º turno, as candidaturas já cadastradas passam pela RN-45.
        Eleição inexistente: 404 `ELEICAO_NAO_ENCONTRADA`.
        """
        eleicao = self._ou_nao_encontrada(self.repository.obter_com_trava_exclusiva(eleicao_id))
        validar_edicao(StatusEleicao(eleicao.status))
        dados = validar_agendamento(
            NovaEleicaoDados(
                descricao=self._ou(alteracoes.descricao, eleicao.descricao),
                data=self._ou(alteracoes.data, eleicao.data),
                turno=self._ou(alteracoes.turno, eleicao.turno),
                horario_abertura=self._ou(alteracoes.horario_abertura, eleicao.horario_abertura),
                horario_encerramento=self._ou(
                    alteracoes.horario_encerramento, eleicao.horario_encerramento
                ),
            ),
            hoje=agora.date(),
        )
        self._conferir_data_e_turno_livres(dados, ignorando_id=eleicao.id)
        validar_candidaturas_no_turno(
            dados.turno, self.repository.contar_candidaturas_por_cargo(eleicao.id)
        )
        eleicao.descricao = dados.descricao
        eleicao.data = dados.data
        eleicao.turno = dados.turno
        eleicao.horario_abertura = dados.horario_abertura
        eleicao.horario_encerramento = dados.horario_encerramento
        self.sessao.commit()
        return self._resumir(eleicao)

    def obter_eleicao(self, eleicao_id: int) -> EleicaoResumo:
        """Consulta uma eleição (RN-19). Levanta 404 `ELEICAO_NAO_ENCONTRADA` se não existir."""
        return self._resumir(self._ou_nao_encontrada(self.repository.buscar_por_id(eleicao_id)))

    def listar_eleicoes(self, status: StatusEleicao | None = None) -> list[EleicaoResumo]:
        """Lista as eleições, da mais antiga à mais nova, com filtro opcional de status (RN-19)."""
        return [self._resumir(eleicao) for eleicao in self.repository.listar(status)]

    def abrir_eleicao(self, eleicao_id: int, agora: datetime) -> EleicaoResumo:
        """Abre a votação (AGENDADA → ABERTA), grava `aberta_em` e faz commit (RN-13, RN-15 a 17).

        Trava a eleição e confere, nesta ordem (`validar_abertura`): status, nenhuma outra aberta,
        data, janela, ao menos uma candidatura e, no 2º turno, 2 por cargo. Grava em cada
        candidatura o retrato do candidato (nome de urna e nascimento). Se duas aberturas
        simultâneas passarem pelas conferências, o índice parcial do banco recusa a segunda
        (409 `OUTRA_ELEICAO_ABERTA`, traduzido pelo tratador de `IntegrityError`).
        Eleição inexistente: 404 `ELEICAO_NAO_ENCONTRADA`.
        """
        eleicao = self._ou_nao_encontrada(self.repository.obter_com_trava_exclusiva(eleicao_id))
        validar_abertura(
            self._resumir(eleicao),
            agora,
            existe_outra_aberta=self.repository.existe_eleicao_aberta(),
            candidaturas_por_cargo=self.repository.contar_candidaturas_por_cargo(eleicao.id),
        )
        self._gravar_retrato_dos_candidatos(eleicao.id)
        eleicao.status = StatusEleicao.ABERTA.value
        eleicao.aberta_em = agora
        self.sessao.commit()
        return self._resumir(eleicao)

    def encerrar_eleicao(self, eleicao_id: int, agora: datetime) -> EleicaoResumo:
        """Encerra a votação (ABERTA → ENCERRADA), registra `encerrada_em` e faz commit (RN-18).

        Pode ser feito a qualquer hora, antes ou depois do horário previsto. A trava exclusiva
        espera as confirmações de voto em andamento (que seguram a trava compartilhada) terminarem:
        depois disso, nenhum voto novo entra. Levanta 409 `TRANSICAO_INVALIDA` se não estiver
        ABERTA e 404 `ELEICAO_NAO_ENCONTRADA` se não existir.
        """
        eleicao = self._ou_nao_encontrada(self.repository.obter_com_trava_exclusiva(eleicao_id))
        validar_encerramento(StatusEleicao(eleicao.status))
        eleicao.status = StatusEleicao.ENCERRADA.value
        eleicao.encerrada_em = agora
        self.sessao.commit()
        return self._resumir(eleicao)

    def obter_eleicao_para_votacao(self, eleicao_id: int) -> EleicaoResumo:
        """Consulta a eleição com `SELECT ... FOR SHARE` para o módulo de votação.

        A trava compartilhada dura até o fim da transação de quem chama e impede
        `encerrar_eleicao` de passar no meio de uma confirmação de voto. **Não faz commit**:
        quem chama controla a transação. Levanta 404 `ELEICAO_NAO_ENCONTRADA` se não existir.
        """
        return self._resumir(
            self._ou_nao_encontrada(self.repository.obter_com_trava_compartilhada(eleicao_id))
        )

    # ------------------------------------------------------------ candidaturas

    def _eleicao_editavel(self, eleicao_id: int) -> Eleicao:
        """Trava a eleição (raiz do agregado) e confere que está AGENDADA (RN-40).

        404 `ELEICAO_NAO_ENCONTRADA` se não existir; 409 `ELEICAO_NAO_EDITAVEL` se não for
        AGENDADA.
        """
        eleicao = self._ou_nao_encontrada(self.repository.obter_com_trava_exclusiva(eleicao_id))
        validar_edicao(StatusEleicao(eleicao.status))
        return eleicao

    def _conferir_partido(self, partido_id: int) -> None:
        """RN-46: levanta 422 `REFERENCIA_INEXISTENTE` (`detalhes.campo` = `partido_id`)."""
        if self.partidos.obter_partido(partido_id) is None:
            raise DadosInvalidos(
                "O partido informado não existe.",
                codigo="REFERENCIA_INEXISTENTE",
                detalhes={"campo": "partido_id"},
            )

    def _conferir_candidato(self, candidato_id: int) -> None:
        """RN-46: levanta 422 `REFERENCIA_INEXISTENTE` (`detalhes.campo` = `candidato_id`)."""
        if not self.candidatos.obter_resumos_de_candidatos([candidato_id]):
            raise DadosInvalidos(
                "O candidato informado não existe.",
                codigo="REFERENCIA_INEXISTENTE",
                detalhes={"campo": "candidato_id"},
            )

    def _conferir_regras_da_candidatura(
        self,
        eleicao: Eleicao,
        cargo: Cargo,
        numero: str,
        ignorando_id: int | None = None,
    ) -> None:
        """RN-42, RN-45 e RN-43, nesta ordem. `ignorando_id` é a candidatura em edição."""
        quantidade = self.repository.contar_candidaturas_no_cargo(eleicao.id, cargo, ignorando_id)
        validar_candidatura(self._resumir(eleicao), cargo, numero, quantidade)
        self._conferir_numero_livre(eleicao.id, cargo, numero, ignorando_id)

    def _conferir_numero_livre(
        self, eleicao_id: int, cargo: Cargo, numero: str, ignorando_id: int | None = None
    ) -> None:
        """RN-43: levanta 409 `NUMERO_JA_UTILIZADO` se outra candidatura usa o número no cargo."""
        if self.repository.existe_numero_no_cargo(eleicao_id, cargo, numero, ignorando_id):
            raise ConflitoDeEstado(
                "Este número já é usado por outra candidatura neste cargo.",
                codigo="NUMERO_JA_UTILIZADO",
            )

    def _gravar_retrato_dos_candidatos(self, eleicao_id: int) -> None:
        """Grava em cada candidatura o nome de urna e o nascimento do candidato de agora.

        Chamada na abertura. Daí em diante a cédula e a apuração usam esse retrato: editar o
        candidato depois não troca o desempate por idade (RN-77) nem os nomes da eleição.
        """
        candidaturas = self.repository.listar_candidaturas(eleicao_id)
        candidatos = self.candidatos.obter_resumos_de_candidatos(
            [c.candidato_id for c in candidaturas]
        )
        for candidatura in candidaturas:
            candidatura.nome_urna = candidatos[candidatura.candidato_id].nome_urna
            candidatura.data_nascimento = candidatos[candidatura.candidato_id].data_nascimento

    def _detalhar(self, candidaturas: list[Candidatura]) -> list[CandidaturaDetalhada]:
        """Junta, em memória, os dados de exibição do candidato e do partido de cada candidatura.

        Nome de urna e nascimento vêm do retrato gravado na abertura ou, se a eleição
        ainda está AGENDADA (retrato nulo), do cadastro atual do candidato. Ordena pela ordem do
        enum `Cargo` e depois pelo número.
        """
        candidatos = self.candidatos.obter_resumos_de_candidatos(
            [c.candidato_id for c in candidaturas]
        )
        partidos = {partido.id: partido for partido in self.partidos.listar_partidos()}
        ordem_dos_cargos = list(Cargo)
        detalhadas = []
        for c in candidaturas:
            candidato = candidatos[c.candidato_id]
            tem_retrato = c.nome_urna is not None
            detalhadas.append(
                CandidaturaDetalhada(
                    id=c.id,
                    eleicao_id=c.eleicao_id,
                    cargo=Cargo(c.cargo),
                    numero=c.numero,
                    candidato_id=c.candidato_id,
                    nome_urna=c.nome_urna if tem_retrato else candidato.nome_urna,
                    data_nascimento=c.data_nascimento if tem_retrato else candidato.data_nascimento,
                    partido_id=c.partido_id,
                    partido_sigla=partidos[c.partido_id].sigla,
                    partido_numero=partidos[c.partido_id].numero,
                )
            )
        return sorted(detalhadas, key=lambda d: (ordem_dos_cargos.index(d.cargo), d.numero))

    def criar_candidatura(
        self, eleicao_id: int, dados: NovaCandidaturaDados, agora: datetime
    ) -> CandidaturaDetalhada:
        """Cria uma candidatura pela raiz do agregado e faz commit (RN-40 a RN-46).

        Trava a eleição; só AGENDADA (RN-40). Candidato e partido precisam existir (RN-46, 422).
        Número com os dígitos do cargo (RN-42) e, no 2º turno, só Governador e Presidente com no
        máximo 2 candidaturas por cargo (RN-45), via `validar_candidatura`.
        Número já usado no cargo → 409 `NUMERO_JA_UTILIZADO` (RN-43); candidato que já tem
        candidatura na eleição → 409 `CANDIDATURA_DUPLICADA` (RN-44). Se o candidato for excluído
        entre a conferência e a gravação, a FK recusa e a resposta é a mesma 422 da RN-46.
        """
        eleicao = self._eleicao_editavel(eleicao_id)
        self._conferir_candidato(dados.candidato_id)
        self._conferir_partido(dados.partido_id)
        self._conferir_regras_da_candidatura(eleicao, dados.cargo, dados.numero)
        if self.repository.existe_candidatura_do_candidato(eleicao.id, dados.candidato_id):
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
        try:
            self.repository.inserir_candidatura(candidatura)
        except IntegrityError as erro:
            self.sessao.rollback()
            if nome_da_restricao(erro) != FK_CANDIDATO_DA_CANDIDATURA:
                raise
            raise DadosInvalidos(
                "O candidato informado não existe.",
                codigo="REFERENCIA_INEXISTENTE",
                detalhes={"campo": "candidato_id"},
            ) from erro
        self.sessao.commit()
        return self._detalhar([candidatura])[0]

    def editar_candidatura(
        self, eleicao_id: int, candidatura_id: int, alteracoes: AlteracoesCandidatura
    ) -> CandidaturaDetalhada:
        """Altera cargo, número e/ou partido (nunca candidato ou eleição) e faz commit (RN-40).

        Mesma trava e mesmas regras da criação, ignorando a própria candidatura nas conferências
        de duplicidade. Candidatura inexistente na eleição: 404 `CANDIDATURA_NAO_ENCONTRADA`.
        """
        eleicao = self._eleicao_editavel(eleicao_id)
        candidatura = self._candidatura_ou_nao_encontrada(eleicao.id, candidatura_id)
        cargo = self._ou(alteracoes.cargo, Cargo(candidatura.cargo))
        numero = self._ou(alteracoes.numero, candidatura.numero)
        partido_id = self._ou(alteracoes.partido_id, candidatura.partido_id)
        self._conferir_partido(partido_id)
        self._conferir_regras_da_candidatura(eleicao, cargo, numero, ignorando_id=candidatura.id)
        candidatura.cargo = cargo.value
        candidatura.numero = numero
        candidatura.partido_id = partido_id
        self.sessao.commit()
        return self._detalhar([candidatura])[0]

    def _candidatura_ou_nao_encontrada(self, eleicao_id: int, candidatura_id: int) -> Candidatura:
        """Devolve a candidatura da eleição ou levanta 404 `CANDIDATURA_NAO_ENCONTRADA`."""
        candidatura = self.repository.buscar_candidatura(eleicao_id, candidatura_id)
        if candidatura is None:
            raise NaoEncontrado("Candidatura não encontrada.", codigo="CANDIDATURA_NAO_ENCONTRADA")
        return candidatura

    def remover_candidatura(self, eleicao_id: int, candidatura_id: int) -> None:
        """Remove a candidatura (só com a eleição AGENDADA, RN-40) e faz commit.

        404 `CANDIDATURA_NAO_ENCONTRADA` se ela não existir nesta eleição.
        """
        eleicao = self._eleicao_editavel(eleicao_id)
        candidatura = self._candidatura_ou_nao_encontrada(eleicao.id, candidatura_id)
        self.repository.remover_candidatura(candidatura)
        self.sessao.commit()

    def listar_candidaturas(
        self, eleicao_id: int, cargo: Cargo | None = None
    ) -> list[CandidaturaDetalhada]:
        """Candidaturas da eleição, ordenadas pelo enum `Cargo` e depois pelo número (RN-40).

        `cargo` filtra. 404 `ELEICAO_NAO_ENCONTRADA` se a eleição não existir.
        """
        self._ou_nao_encontrada(self.repository.buscar_por_id(eleicao_id))
        return self._detalhar(self.repository.listar_candidaturas(eleicao_id, cargo))

    def candidaturas_do_usuario(self, usuario_id: int) -> list[CandidaturaDetalhada]:
        """As candidaturas do candidato logado, em todas as eleições (RN-47).

        Ordenadas por eleição, cargo e número. Credencial sem candidato (por exemplo, um eleitor)
        devolve lista vazia; quem barra o acesso é a rota (só o perfil CANDIDATO).
        """
        candidato = self.candidatos.obter_candidato_do_usuario(usuario_id)
        if candidato is None:
            return []
        candidaturas = self._detalhar(
            self.repository.listar_candidaturas_do_candidato(candidato.id)
        )
        return sorted(candidaturas, key=lambda c: c.eleicao_id)
