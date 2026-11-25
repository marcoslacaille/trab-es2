"""Testes do `PartidoService`: a regra de sigla, nome e número, e o que ele pede ao repository."""

from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.dto.partido_dto import NovoPartidoDados
from app.repositories.partido_repository import PartidoRepository
from app.services.partido_service import PartidoService, validar_partido

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_partido_valido_vem_normalizado():
    """RN-32: a sigla vira maiúscula e o nome perde os espaços das pontas."""
    dados = validar_partido(
        NovoPartidoDados(sigla=" pino ", nome="  Partido da Inovação ", numero=10)
    )

    assert dados == NovoPartidoDados(sigla="PINO", nome="Partido da Inovação", numero=10)


@pytest.mark.parametrize(
    "recusas",
    [
        pytest.param([{"sigla": "A"}, {"sigla": "ABCDEFGHIJK"}, {"sigla": "AB-C"}], id="sigla"),
        pytest.param(
            [{"numero": 9}, {"numero": 100}, {"nome": "   "}, {"nome": "x" * 101}],
            id="numero-e-nome",
        ),
    ],
)
def test_partido_fora_do_formato_e_recusado(recusas):
    """RN-32: sigla de 2 a 10 letras ou dígitos, número de 10 a 99 e nome de 1 a 100 caracteres."""
    for mudancas in recusas:
        dados = NovoPartidoDados(**{"sigla": "PINO", "nome": "Partido", "numero": 10, **mudancas})

        with pytest.raises(DadosInvalidos) as erro:
            validar_partido(dados)

        assert erro.value.codigo == "DADOS_INVALIDOS", mudancas


def test_criar_partido_repetido_responde_409():
    """RN-32: sigla, nome ou número já usados dão `PARTIDO_DUPLICADO`, sem inserir nem commit."""
    service = PartidoService(sessao=Mock(), repository=Mock(spec=PartidoRepository))
    service.repository.existe_partido_com.return_value = True

    with pytest.raises(ConflitoDeEstado) as erro:
        service.criar_partido(NovoPartidoDados(sigla=" pino ", nome="Partido", numero=10), AGORA)

    assert erro.value.codigo == "PARTIDO_DUPLICADO"
    service.repository.existe_partido_com.assert_called_once_with("PINO", "Partido", 10)
    service.repository.inserir_partido.assert_not_called()
    service.sessao.commit.assert_not_called()
