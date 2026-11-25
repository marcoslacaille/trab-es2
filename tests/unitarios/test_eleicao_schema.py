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


def uma_eleicao_aberta() -> EleicaoResumo:
    """Eleição ABERTA de 25/11/2026, das 08:00 às 17:00."""
    return EleicaoResumo(
        id=7,
        descricao="Eleições Gerais 2026",
        data=date(2026, 11, 25),
        turno=1,
        horario_abertura=time(8, 0),
        horario_encerramento=time(17, 0),
        status=StatusEleicao.ABERTA,
        aberta_em=datetime(2026, 11, 25, 8, 0, tzinfo=FUSO),
        encerrada_em=None,
        criado_em=datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    )


@pytest.mark.parametrize(
    ("perfil", "esperados"),
    [
        pytest.param(
            Perfil.CHEFE_SECAO,
            [
                LINK_SELF,
                ("encerrar", "POST", f"{BASE}/encerramento"),
                ("apuracao-parcial", "GET", f"{APURACAO}/parcial"),
            ],
            id="chefe-com-eleicao-aberta",
        ),
        pytest.param(
            Perfil.ELEITOR,
            [
                LINK_SELF,
                ("cedula", "GET", "/api/v1/votacao/eleicoes/7/cedula"),
                ("apuracao-parcial", "GET", f"{APURACAO}/parcial"),
            ],
            id="eleitor-com-eleicao-aberta",
        ),
        pytest.param("VISITANTE", [LINK_SELF], id="perfil-desconhecido"),
    ],
)
def test_links_dependem_do_perfil_e_do_status(perfil, esperados):
    """RN-19: os links mudam com o perfil e o status; um perfil desconhecido só recebe o `self`."""
    links = links_da_eleicao(uma_eleicao_aberta(), perfil)

    assert [(link.rel, link.metodo, link.href) for link in links] == esperados
