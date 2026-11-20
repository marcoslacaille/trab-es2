from datetime import date

import pytest

from app.compartilhado.dominio import Cargo, numero_valido_para_cargo
from app.compartilhado.validadores import calcular_idade, cpf_valido, normalizar_cpf, so_digitos

# Quantidade de dígitos de cada cargo, escrita aqui de propósito (e não lida de
# DIGITOS_POR_CARGO), para o teste conferir a regra e não repetir o código.
DIGITOS_ESPERADOS = {
    Cargo.DEPUTADO_FEDERAL: 4,
    Cargo.DEPUTADO_ESTADUAL: 5,
    Cargo.SENADOR: 3,
    Cargo.GOVERNADOR: 2,
    Cargo.PRESIDENTE: 2,
}


def test_aceita_cpf_valido_conhecido():
    """TU-01 / RN-07: o CPF 529.982.247-25 tem os dígitos verificadores corretos."""
    cpf = normalizar_cpf("529.982.247-25")

    assert cpf_valido(cpf) is True


@pytest.mark.parametrize("cpf", ["52998224726", "52998224735", "52998224700"])
def test_recusa_cpf_com_digito_verificador_errado(cpf):
    """TU-02 / RN-07: troca de qualquer dos dois dígitos verificadores invalida o CPF."""
    assert cpf_valido(cpf) is False


@pytest.mark.parametrize("cpf", [str(digito) * 11 for digito in range(10)])
def test_recusa_cpf_com_todos_os_digitos_iguais(cpf):
    """TU-03 / RN-07: 111.111.111-11 passa na conta dos dígitos, mas não é um CPF válido."""
    assert cpf_valido(cpf) is False


@pytest.mark.parametrize(
    "valor",
    ["529.982.247-25", "52998224725", " 529.982.247-25 ", "529982247-25", "529.98224725"],
)
def test_normaliza_cpf_com_e_sem_pontuacao(valor):
    """TU-04 / RN-07: com ou sem pontuação, o resultado são só os 11 dígitos."""
    assert normalizar_cpf(valor) == "52998224725"


@pytest.mark.parametrize(
    "valor",
    ["", "abc.def.ghi-jk", "529.982.247-2a", "5299822472", "529982247255", "529,982,247-25"],
)
def test_recusa_cpf_com_letras_ou_tamanho_errado_na_normalizacao(valor):
    """TU-04 / RN-07: letras, tamanho errado ou pontuação fora do padrão viram texto vazio."""
    assert normalizar_cpf(valor) == ""


def test_recusa_cpf_com_digitos_de_outro_alfabeto():
    """TU-04 / RN-07 (D-010): dígitos arábico-índicos não são dígitos de CPF."""
    cpf_arabico = "٢٩١٤١٧٧٧٦٣٨"

    assert normalizar_cpf(cpf_arabico) == ""
    assert cpf_valido(cpf_arabico) is False


@pytest.mark.parametrize(("texto", "esperado"), [("0123456789", True), ("٢٩", False), ("", False)])
def test_so_digitos_aceita_apenas_ascii(texto, esperado):
    """D-010: só os dígitos de 0 a 9 valem; texto vazio e outros alfabetos, não."""
    assert so_digitos(texto) is esperado


@pytest.mark.parametrize(
    ("nascimento", "referencia", "idade"),
    [
        (date(2000, 6, 15), date(2026, 6, 14), 25),  # um dia antes do aniversário
        (date(2000, 6, 15), date(2026, 6, 15), 26),  # no dia do aniversário
        (date(2000, 6, 15), date(2026, 6, 16), 26),  # um dia depois
        (date(2004, 2, 29), date(2025, 2, 28), 20),  # nascido em 29/02, ano não bissexto, antes
        (date(2004, 2, 29), date(2025, 3, 1), 21),  # nascido em 29/02, ano não bissexto, depois
        (date(2004, 2, 29), date(2028, 2, 29), 24),  # nascido em 29/02, no aniversário de verdade
    ],
)
def test_calcula_idade_antes_e_depois_do_aniversario(nascimento, referencia, idade):
    """TU-05 / RN-22: a idade só sobe no dia do aniversário (29/02 comemora em 01/03)."""
    assert calcular_idade(nascimento, referencia) == idade


def _casos_de_numero_por_cargo():
    """Por cargo: um número válido e quatro inválidos (curto, longo, zero na frente, letras)."""
    for cargo, digitos in DIGITOS_ESPERADOS.items():
        yield pytest.param(cargo, "1" * digitos, True, id=f"{cargo}-valido")
        yield pytest.param(cargo, "1" * (digitos - 1), False, id=f"{cargo}-curto")
        yield pytest.param(cargo, "1" * (digitos + 1), False, id=f"{cargo}-longo")
        yield pytest.param(cargo, "0" + "1" * (digitos - 1), False, id=f"{cargo}-zero-a-esquerda")
        yield pytest.param(cargo, "A" * digitos, False, id=f"{cargo}-letras")


@pytest.mark.parametrize(("cargo", "numero", "esperado"), list(_casos_de_numero_por_cargo()))
def test_valida_numero_conforme_os_digitos_do_cargo(cargo, numero, esperado):
    """TU-06 / RN-42: só dígitos, sem zero à esquerda, na quantidade exata do cargo."""
    assert numero_valido_para_cargo(numero, cargo) is esperado


def test_recusa_numero_com_digitos_de_outro_alfabeto():
    """TU-06 / RN-42 (D-010): '١٠' tem 2 dígitos arábico-índicos, mas não é um número válido."""
    assert numero_valido_para_cargo("١٠", Cargo.PRESIDENTE) is False
