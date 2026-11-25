"""Validadores puros do `core`: CPF, idade, número da candidatura por cargo e caractere nulo."""

from datetime import date

import pytest

from app.core.validadores import (
    calcular_idade,
    cpf_valido,
    normalizar_cpf,
    sem_caractere_nulo,
)
from app.models.enums import Cargo, numero_valido_para_cargo

# Quantidade de dígitos de cada cargo, escrita aqui de propósito (e não lida de
# DIGITOS_POR_CARGO), para o teste conferir a regra e não repetir o código.
DIGITOS_ESPERADOS = {
    Cargo.DEPUTADO_FEDERAL: 4,
    Cargo.DEPUTADO_ESTADUAL: 5,
    Cargo.SENADOR: 3,
    Cargo.GOVERNADOR: 2,
    Cargo.PRESIDENTE: 2,
}


def test_cpf_valido_e_aceito():
    """RN-07: o CPF 529.982.247-25 tem os dígitos verificadores corretos."""
    cpf = normalizar_cpf("529.982.247-25")

    assert cpf_valido(cpf) is True


def test_cpf_com_digito_verificador_errado_e_recusado():
    """RN-07: trocar qualquer dos dois dígitos verificadores invalida o CPF."""
    for cpf in ("52998224726", "52998224735"):  # só o 2º dígito errado; só o 1º errado
        assert cpf_valido(cpf) is False, cpf


def test_cpf_com_todos_os_digitos_iguais_e_recusado():
    """RN-07: 111.111.111-11 passa na conta dos dígitos, mas não é um CPF válido."""
    assert cpf_valido("11111111111") is False


def test_cpf_e_normalizado_com_e_sem_pontuacao():
    """RN-07: com ou sem pontuação, e com espaços nas pontas, o resultado são os 11 dígitos."""
    for valor in ("529.982.247-25", "52998224725", " 529.982.247-25 "):
        assert normalizar_cpf(valor) == "52998224725", valor


@pytest.mark.parametrize(
    "valores",
    [
        pytest.param(
            [
                "abc.def.ghi-jk",
                "529.982.247-2a",
                "٢٩١٤١٧٧٧٦٣٨",
            ],  # o último: dígitos arábico-índicos
            id="letras-ou-outro-alfabeto",
        ),
        pytest.param(["", "5299822472", "529982247255", "529,982,247-25"], id="tamanho-errado"),
    ],
)
def test_cpf_com_letras_tamanho_errado_ou_outro_alfabeto_vira_texto_vazio(valores):
    """RN-07: letras, dígitos de outro alfabeto, tamanho errado ou pontuação fora do padrão."""
    for valor in valores:
        assert normalizar_cpf(valor) == "", valor
        assert cpf_valido(valor) is False, valor


@pytest.mark.parametrize(
    ("nascimento", "idades"),
    [
        pytest.param(
            date(2000, 6, 15),
            [(date(2026, 6, 14), 25), (date(2026, 6, 15), 26)],
            id="vespera-do-aniversario",
        ),
        pytest.param(
            date(2004, 2, 29),
            [(date(2025, 2, 28), 20), (date(2025, 3, 1), 21), (date(2028, 2, 29), 24)],
            id="nascido-em-29-de-fevereiro",
        ),
    ],
)
def test_idade_so_sobe_no_aniversario(nascimento, idades):
    """RN-22: a idade só sobe no dia do aniversário (quem nasceu em 29/02 comemora em 01/03)."""
    for referencia, idade in idades:
        assert calcular_idade(nascimento, referencia) == idade, referencia


def _numeros_com_a_quantidade_de_digitos():
    """Por cargo: um número válido, um curto e um longo demais."""
    for cargo, digitos in DIGITOS_ESPERADOS.items():
        yield cargo, "1" * digitos, True
        yield cargo, "1" * (digitos - 1), False
        yield cargo, "1" * (digitos + 1), False


def _numeros_que_parecem_certos():
    """Com a quantidade certa de caracteres, mas que não valem: zero na frente e letras."""
    for cargo, digitos in DIGITOS_ESPERADOS.items():
        yield cargo, "0" + "1" * (digitos - 1), False
        yield cargo, "A" * digitos, False
    yield Cargo.PRESIDENTE, "١٠", False  # 2 dígitos arábico-índicos


@pytest.mark.parametrize(
    "casos",
    [
        pytest.param(list(_numeros_com_a_quantidade_de_digitos()), id="digitos-de-cada-cargo"),
        pytest.param(list(_numeros_que_parecem_certos()), id="zero-letras-e-outro-alfabeto"),
    ],
)
def test_numero_conforme_os_digitos_do_cargo(casos):
    """RN-42: só dígitos de 0 a 9, sem zero à esquerda, na quantidade exata do cargo."""
    for cargo, numero, esperado in casos:
        assert numero_valido_para_cargo(numero, cargo) is esperado, (cargo, numero)


def test_caractere_nulo_e_recusado():
    """RN-08: o PostgreSQL não aceita o caractere nulo em texto; o validador recusa antes."""
    assert sem_caractere_nulo("Ana Maria") == "Ana Maria"
    assert sem_caractere_nulo(None) is None
    with pytest.raises(ValueError, match="caractere nulo"):
        sem_caractere_nulo("Ana\x00Maria")
