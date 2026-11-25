"""Schema de eleição: os links HATEOAS que cada perfil recebe, sem banco e sem HTTP."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.dto.eleicao_dto import EleicaoResumo
from app.models.enums import Perfil, StatusEleicao
from app.schemas.eleicao_schema import links_da_eleicao

FUSO = ZoneInfo("America/Sao_Paulo")
BASE = "/api/v1/eleicoes/7"
APURACAO = "/api/v1/apuracao/eleicoes/7"
LINK_SELF = ("self", "GET", BASE)
CANDIDATURAS = ("candidaturas", "GET", f"{BASE}/candidaturas")
PARCIAL = ("apuracao-parcial", "GET", f"{APURACAO}/parcial")
RESULTADO = ("resultado", "GET", f"{APURACAO}/resultado")
AGENDADA, ABERTA, ENCERRADA = StatusEleicao.AGENDADA, StatusEleicao.ABERTA, StatusEleicao.ENCERRADA


def uma_eleicao(status: StatusEleicao) -> EleicaoResumo:
    """Eleição de 25/11/2026, das 08:00 às 17:00, no status pedido."""
    return EleicaoResumo(
        id=7,
        descricao="Eleições Gerais 2026",
        data=date(2026, 11, 25),
        turno=1,
        horario_abertura=time(8, 0),
        horario_encerramento=time(17, 0),
        status=status,
        aberta_em=None if status == AGENDADA else datetime(2026, 11, 25, 8, 0, tzinfo=FUSO),
        encerrada_em=datetime(2026, 11, 25, 17, 0, tzinfo=FUSO) if status == ENCERRADA else None,
        criado_em=datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    )


@pytest.mark.parametrize(
    ("perfil", "status", "esperados"),
    [
        pytest.param(
            Perfil.CHEFE_SECAO,
            AGENDADA,
            [
                LINK_SELF,
                ("editar", "PATCH", BASE),
                CANDIDATURAS,
                ("nova-candidatura", "POST", f"{BASE}/candidaturas"),
                ("abrir", "POST", f"{BASE}/abertura"),
            ],
            id="chefe-com-eleicao-agendada",
        ),
        pytest.param(Perfil.ELEITOR, AGENDADA, [LINK_SELF], id="eleitor-com-eleicao-agendada"),
        pytest.param(
            Perfil.CHEFE_SECAO,
            ABERTA,
            [LINK_SELF, CANDIDATURAS, ("encerrar", "POST", f"{BASE}/encerramento"), PARCIAL],
            id="chefe-com-eleicao-aberta",
        ),
        pytest.param(
            Perfil.ELEITOR,
            ABERTA,
            [LINK_SELF, ("cedula", "GET", "/api/v1/votacao/eleicoes/7/cedula"), PARCIAL],
            id="eleitor-com-eleicao-aberta",
        ),
        pytest.param(Perfil.CANDIDATO, ABERTA, [LINK_SELF, PARCIAL], id="candidato-com-aberta"),
        pytest.param(
            Perfil.CHEFE_SECAO,
            ENCERRADA,
            [LINK_SELF, CANDIDATURAS, RESULTADO],
            id="chefe-com-eleicao-encerrada",
        ),
        pytest.param(
            Perfil.CANDIDATO, ENCERRADA, [LINK_SELF, RESULTADO], id="candidato-com-encerrada"
        ),
        pytest.param("VISITANTE", ABERTA, [LINK_SELF], id="perfil-desconhecido"),
    ],
)
def test_links_dependem_do_perfil_e_do_status(perfil, status, esperados):
    """RN-19: os links mudam com o perfil e o status; um perfil desconhecido só recebe o `self`."""
    links = links_da_eleicao(uma_eleicao(status), perfil)

    assert [(link.rel, link.metodo, link.href) for link in links] == esperados
