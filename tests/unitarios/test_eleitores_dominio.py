from datetime import date

import pytest

from app.core.exceptions import DadosInvalidos
from app.services.eleitor_service import validar_idade_eleitor, validar_titulo_eleitor

HOJE = date(2026, 11, 25)


def test_aceita_eleitor_com_16_anos_completos_hoje():
    """RN-22: quem faz 16 anos exatamente hoje já pode ser cadastrado."""
    validar_idade_eleitor(date(2010, 11, 25), HOJE)


def test_aceita_eleitor_adulto():
    """RN-22: um adulto passa pela regra de idade mínima."""
    validar_idade_eleitor(date(1990, 4, 12), HOJE)


def test_recusa_eleitor_que_faz_16_anos_amanha():
    """RN-22: um dia a menos para os 16 anos completos e o cadastro é recusado."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_idade_eleitor(date(2010, 11, 26), HOJE)

    assert erro.value.codigo == "IDADE_MINIMA"


@pytest.mark.parametrize("nascimento", [date(2027, 1, 1), HOJE])
def test_recusa_nascimento_que_nao_esta_no_passado(nascimento):
    """RN-22: nascimento no futuro (ou hoje) é recusado com `IDADE_MINIMA`."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_idade_eleitor(nascimento, HOJE)

    assert erro.value.codigo == "IDADE_MINIMA"


def test_aceita_titulo_com_12_digitos():
    """RN-21: título com exatamente 12 dígitos é aceito."""
    validar_titulo_eleitor("100000000001")


@pytest.mark.parametrize(
    "titulo",
    [
        "10000000000",  # 11 dígitos
        "1000000000011",  # 13 dígitos
        "10000000000a",  # letra
        "١٠٠٠٠٠٠٠٠٠٠١",  # 12 dígitos arábico-índicos, que só o `isdigit()` aceitaria
        "",
    ],
)
def test_recusa_titulo_fora_do_formato(titulo):
    """RN-21: título de tamanho errado, com letras ou com dígitos de outros alfabetos."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_titulo_eleitor(titulo)

    assert erro.value.codigo == "DADOS_INVALIDOS"
