"""Service de apuração: casos de uso somente de leitura, sem tabelas próprias.

Combina contagens, candidaturas e eleitores aptos, lidos num mesmo instante (`REPEATABLE READ`).
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.dto.apuracao_dto import Apuracao, ComparecimentoEleicao, LinhaApuracao, ResultadoCargo
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import ContagemVoto
from app.models.enums import Cargo, Perfil, SituacaoCargo, StatusEleicao, TipoVoto
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService
from app.services.votacao_service import VotacaoService

PREFIXO_DA_API = "/api/v1"

CRITERIO_MAIOR_VOTACAO = "MAIOR_VOTACAO"
CRITERIO_DESEMPATE_POR_IDADE = "DESEMPATE_POR_IDADE"


def percentual(votos: int, validos: int) -> Decimal:
    """Percentual sobre votos válidos, 2 casas, meio para cima (RN-76)."""
    if validos == 0:
        return Decimal("0.00")
    return (Decimal(votos) * 100 / Decimal(validos)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def definir_mais_votado(
    linhas: list[LinhaApuracao],
) -> tuple[LinhaApuracao | None, SituacaoCargo, str | None]:
    """Linhas já ordenadas por votos. Empate: mais idoso; persistindo, EMPATE (RN-77, RN-78)."""
    if not linhas or linhas[0].votos == 0:
        return None, SituacaoCargo.SEM_VOTOS_VALIDOS, None
    lideres = [linha for linha in linhas if linha.votos == linhas[0].votos]
    if len(lideres) == 1:
        return lideres[0], SituacaoCargo.DEFINIDO, CRITERIO_MAIOR_VOTACAO
    nascimento_mais_antigo = min(linha.data_nascimento for linha in lideres)
    mais_idosos = [linha for linha in lideres if linha.data_nascimento == nascimento_mais_antigo]
    if len(mais_idosos) == 1:
        return mais_idosos[0], SituacaoCargo.DEFINIDO, CRITERIO_DESEMPATE_POR_IDADE
    return None, SituacaoCargo.EMPATE, None


def _separar_contagens(contagens: list[ContagemVoto]) -> tuple[int, int, dict[int, int]]:
    """Devolve (brancos, nulos, votos nominais por id de candidatura) de um cargo."""
    brancos = sum(c.total for c in contagens if c.tipo == TipoVoto.BRANCO)
    nulos = sum(c.total for c in contagens if c.tipo == TipoVoto.NULO)
    nominais = {
        c.candidatura_id: c.total
        for c in contagens
        if c.tipo == TipoVoto.NOMINAL and c.candidatura_id is not None
    }
    return brancos, nulos, nominais


def apurar_cargo(
    cargo: Cargo,
    candidaturas_do_cargo: list[CandidaturaDetalhada],
    contagens_do_cargo: list[ContagemVoto],
) -> ResultadoCargo:
    """Monta a apuração de um cargo (RN-75 a RN-78).

    Separa brancos e nulos dos nominais; cria uma linha por candidatura, inclusive com 0 votos;
    calcula os percentuais sobre os votos válidos (só os nominais); ordena por votos
    (decrescente) e depois por número; e decide o mais votado.
    """
    brancos, nulos, votos_por_candidatura = _separar_contagens(contagens_do_cargo)
    votos_validos = sum(votos_por_candidatura.values())

    linhas = [
        LinhaApuracao(
            numero=candidatura.numero,
            nome_urna=candidatura.nome_urna,
            partido_sigla=candidatura.partido_sigla,
            votos=votos_por_candidatura.get(candidatura.id, 0),
            percentual_validos=percentual(
                votos_por_candidatura.get(candidatura.id, 0), votos_validos
            ),
            data_nascimento=candidatura.data_nascimento,
        )
        for candidatura in candidaturas_do_cargo
    ]
    linhas.sort(key=lambda linha: (-linha.votos, linha.numero))
    mais_votado, situacao, criterio = definir_mais_votado(linhas)
    return ResultadoCargo(
        cargo=cargo,
        total_votos=votos_validos + brancos + nulos,
        votos_validos=votos_validos,
        brancos=brancos,
        nulos=nulos,
        situacao=situacao,
        criterio=criterio,
        mais_votado=mais_votado,
        candidatos=linhas,
    )


def _exigir_status(eleicao: EleicaoResumo, esperado: StatusEleicao) -> None:
    """RN-70: a parcial só existe com a eleição ABERTA e o resultado só com a ENCERRADA."""
    if eleicao.status == esperado:
        return
    detalhes: dict = {"status": eleicao.status.value}
    if eleicao.status == StatusEleicao.ENCERRADA:
        detalhes["resultado"] = f"{PREFIXO_DA_API}/apuracao/eleicoes/{eleicao.id}/resultado"
    quando = "a parcial" if esperado == StatusEleicao.ABERTA else "o resultado final"
    raise ConflitoDeEstado(
        f"Só é possível consultar {quando} com a eleição {esperado.value}.",
        codigo="APURACAO_INDISPONIVEL",
        detalhes=detalhes,
    )


class ApuracaoService:
    """Service de apuração: só leitura, sem commit (não há nada a gravar).

    Toda a apuração lê o banco num mesmo instante (transação `REPEATABLE READ`, D-146).
    """

    def __init__(
        self,
        sessao: Session,
        votacao: VotacaoService | None = None,
        eleicoes: EleicaoService | None = None,
        eleitores: EleitorService | None = None,
    ) -> None:
        self.sessao = sessao
        self.eleicoes = eleicoes or EleicaoService(sessao)
        self.eleitores = eleitores or EleitorService(sessao)
        self.votacao = votacao or VotacaoService(
            sessao, eleicoes=self.eleicoes, eleitores=self.eleitores
        )

    def _ler_num_mesmo_instante(self) -> None:
        """Abre uma transação `REPEATABLE READ`: toda leitura da apuração vê o mesmo instante.

        Sem isso, um voto confirmado entre a contagem dos votos e a dos votantes faria a mesma
        resposta mostrar, por exemplo, 1 votante e 0 votos (D-146). O nível de isolamento só pode
        ser escolhido no começo de uma transação, então a leitura feita antes (a do usuário
        logado) é encerrada com `rollback`. Não há nada gravado para desfazer.
        """
        self.sessao.rollback()
        self.sessao.connection(execution_options={"isolation_level": "REPEATABLE READ"})

    def _cargo_do_candidato(
        self, usuario: UsuarioAutenticado, eleicao_id: int, cargo_pedido: Cargo | None
    ) -> Cargo:
        """RN-72: o Candidato só vê o cargo da sua candidatura nesta eleição."""
        minhas = [
            c
            for c in self.eleicoes.candidaturas_do_usuario(usuario.id)
            if c.eleicao_id == eleicao_id
        ]
        if not minhas:
            raise AcessoNegado(
                "Você não tem candidatura nesta eleição.", codigo="SEM_CANDIDATURA_NA_ELEICAO"
            )
        meu_cargo = minhas[0].cargo
        if cargo_pedido is not None and cargo_pedido != meu_cargo:
            raise AcessoNegado(
                "Você só pode acompanhar o cargo da sua candidatura.",
                codigo="CARGO_NAO_PERMITIDO",
                detalhes={"cargo_permitido": meu_cargo.value},
            )
        return meu_cargo

    def _apurar(
        self,
        eleicao: EleicaoResumo,
        cargos_pedidos: list[Cargo] | None,
        tipo: str,
        agora: datetime,
    ) -> Apuracao:
        """Monta a apuração dos cargos pedidos (`None` = todos os disputados) e o comparecimento."""
        candidaturas = self.eleicoes.listar_candidaturas(eleicao.id)
        contagens = self.votacao.contar_votos(eleicao.id)
        comparecimento = self.votacao.contar_comparecimento(eleicao.id)
        # `aberta_em` existe sempre que a eleição está ABERTA ou ENCERRADA (RN-15).
        aptos = self.eleitores.contar_aptos(eleicao.aberta_em)

        disputados = sorted({c.cargo for c in candidaturas}, key=list(Cargo).index)
        if cargos_pedidos is None:
            cargos = disputados
        elif cargos_pedidos[0] in disputados:
            cargos = cargos_pedidos
        else:
            raise DadosInvalidos(
                "Este cargo não é disputado nesta eleição.",
                codigo="CARGO_NAO_DISPUTADO",
                detalhes={"cargo": cargos_pedidos[0].value},
            )
        resultados: list[ResultadoCargo] = [
            apurar_cargo(
                cargo,
                [c for c in candidaturas if c.cargo == cargo],
                [c for c in contagens if c.cargo == cargo],
            )
            for cargo in cargos
        ]
        votantes = comparecimento.eleitores_que_votaram
        return Apuracao(
            eleicao_id=eleicao.id,
            tipo=tipo,
            status_eleicao=eleicao.status,
            gerado_em=agora,
            comparecimento=ComparecimentoEleicao(
                eleitores_aptos=aptos, votantes=votantes, abstencao=aptos - votantes
            ),
            cargos=resultados,
        )

    def apuracao_parcial(
        self,
        usuario: UsuarioAutenticado,
        eleicao_id: int,
        cargo_pedido: Cargo | None,
        agora: datetime,
    ) -> Apuracao:
        """Acompanhamento parcial, calculado no momento da consulta (RN-70 a RN-72, RN-74 a RN-79).

        Eleição inexistente: 404. Status diferente de ABERTA: 409 `APURACAO_INDISPONIVEL`.
        Candidato: só o cargo da sua candidatura (403 `SEM_CANDIDATURA_NA_ELEICAO` ou
        `CARGO_NAO_PERMITIDO`). Eleitor e Chefe: o cargo pedido ou todos os disputados; cargo que
        não é disputado: 422 `CARGO_NAO_DISPUTADO`. Aqui `mais_votado` é "quem lidera até agora".
        """
        self._ler_num_mesmo_instante()
        eleicao = self.eleicoes.obter_eleicao(eleicao_id)
        _exigir_status(eleicao, StatusEleicao.ABERTA)
        if usuario.perfil == Perfil.CANDIDATO:
            cargos = [self._cargo_do_candidato(usuario, eleicao_id, cargo_pedido)]
        else:
            cargos = [cargo_pedido] if cargo_pedido is not None else None
        return self._apurar(eleicao, cargos, "PARCIAL", agora)

    def resultado_final(
        self,
        usuario: UsuarioAutenticado,
        eleicao_id: int,
        cargo_pedido: Cargo | None,
        agora: datetime,
    ) -> Apuracao:
        """Resultado final, visível a todos os perfis autenticados (RN-70, RN-73 a RN-79).

        Eleição inexistente: 404. Status diferente de ENCERRADA: 409 `APURACAO_INDISPONIVEL`.
        O `usuario` não muda nada (qualquer perfil vê todos os cargos); a assinatura é a mesma da
        parcial, como no PLANO. Cargo que não é disputado: 422 `CARGO_NAO_DISPUTADO`.
        """
        self._ler_num_mesmo_instante()
        eleicao = self.eleicoes.obter_eleicao(eleicao_id)
        _exigir_status(eleicao, StatusEleicao.ENCERRADA)
        cargos = [cargo_pedido] if cargo_pedido is not None else None
        return self._apurar(eleicao, cargos, "FINAL", agora)
