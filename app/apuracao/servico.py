"""Casos de uso da apuração (somente leitura, sem tabelas próprias).

Combina as contagens de `votacao`, as candidaturas de `eleicoes` e os eleitores aptos de
`eleitores`. Nenhuma função faz commit: não há nada a gravar.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.apuracao import dominio
from app.apuracao.dominio import Apuracao, ComparecimentoEleicao, ResultadoCargo
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.eleicoes import servico as eleicoes_servico
from app.eleicoes.dominio import EleicaoResumo, StatusEleicao
from app.eleitores import servico as eleitores_servico
from app.identidade.servico import Perfil, UsuarioAutenticado
from app.votacao import servico as votacao_servico

PREFIXO_DA_API = "/api/v1"


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
        for c in eleicoes_servico.candidaturas_do_usuario(sessao, usuario.id)
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
    candidaturas = eleicoes_servico.listar_candidaturas(sessao, eleicao.id)
    contagens = votacao_servico.contar_votos(sessao, eleicao.id)
    comparecimento = votacao_servico.contar_comparecimento(sessao, eleicao.id)
    # `aberta_em` existe sempre que a eleição está ABERTA ou ENCERRADA (RN-15).
    aptos = eleitores_servico.contar_aptos(sessao, eleicao.aberta_em)

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
    eleicao = eleicoes_servico.obter_eleicao(sessao, eleicao_id)
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
    eleicao = eleicoes_servico.obter_eleicao(sessao, eleicao_id)
    _exigir_status(eleicao, StatusEleicao.ENCERRADA)
    cargos = [cargo_pedido] if cargo_pedido is not None else None
    return _apurar(sessao, eleicao, cargos, "FINAL", agora)
