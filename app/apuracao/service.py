"""Service da apuração: casos de uso somente de leitura, sem tabelas próprias.

Combina as contagens de `votacao`, as candidaturas de `eleicoes` e os eleitores aptos de
`eleitores`. Nenhuma função faz commit: não há nada a gravar. Toda a apuração lê o banco num
mesmo instante (transação `REPEATABLE READ`, D-146).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.apuracao import dominio
from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.dto.apuracao_dto import Apuracao, ComparecimentoEleicao, ResultadoCargo
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.eleicoes import service as eleicoes_service
from app.eleitores import service as eleitores_service
from app.models.enums import Cargo, Perfil, StatusEleicao
from app.votacao import service as votacao_service

PREFIXO_DA_API = "/api/v1"


def _ler_num_mesmo_instante(sessao: Session) -> None:
    """Abre uma transação `REPEATABLE READ`: todas as leituras da apuração veem o mesmo instante.

    Sem isso, um voto confirmado entre a contagem dos votos e a dos votantes faria a mesma
    resposta mostrar, por exemplo, 1 votante e 0 votos (D-146). O nível de isolamento só pode ser
    escolhido no começo de uma transação, então a leitura feita antes (a do usuário logado) é
    encerrada com `rollback`. Não há nada gravado para desfazer.
    """
    sessao.rollback()
    sessao.connection(execution_options={"isolation_level": "REPEATABLE READ"})


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


def _cargo_do_candidato(
    sessao: Session, usuario: UsuarioAutenticado, eleicao_id: int, cargo_pedido: Cargo | None
) -> Cargo:
    """RN-72: o Candidato só vê o cargo da sua candidatura nesta eleição."""
    minhas = [
        c
        for c in eleicoes_service.candidaturas_do_usuario(sessao, usuario.id)
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
    sessao: Session,
    eleicao: EleicaoResumo,
    cargos_pedidos: list[Cargo] | None,
    tipo: str,
    agora: datetime,
) -> Apuracao:
    """Monta a apuração dos cargos pedidos (`None` = todos os disputados) e o comparecimento."""
    candidaturas = eleicoes_service.listar_candidaturas(sessao, eleicao.id)
    contagens = votacao_service.contar_votos(sessao, eleicao.id)
    comparecimento = votacao_service.contar_comparecimento(sessao, eleicao.id)
    # `aberta_em` existe sempre que a eleição está ABERTA ou ENCERRADA (RN-15).
    aptos = eleitores_service.contar_aptos(sessao, eleicao.aberta_em)

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
        dominio.apurar_cargo(
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
    sessao: Session,
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
    _ler_num_mesmo_instante(sessao)
    eleicao = eleicoes_service.obter_eleicao(sessao, eleicao_id)
    _exigir_status(eleicao, StatusEleicao.ABERTA)
    if usuario.perfil == Perfil.CANDIDATO:
        cargos = [_cargo_do_candidato(sessao, usuario, eleicao_id, cargo_pedido)]
    else:
        cargos = [cargo_pedido] if cargo_pedido is not None else None
    return _apurar(sessao, eleicao, cargos, "PARCIAL", agora)


def resultado_final(
    sessao: Session,
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
    _ler_num_mesmo_instante(sessao)
    eleicao = eleicoes_service.obter_eleicao(sessao, eleicao_id)
    _exigir_status(eleicao, StatusEleicao.ENCERRADA)
    cargos = [cargo_pedido] if cargo_pedido is not None else None
    return _apurar(sessao, eleicao, cargos, "FINAL", agora)
