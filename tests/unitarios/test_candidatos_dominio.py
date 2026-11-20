from datetime import date

import pytest

from app.candidatos.dominio import (
    NovoPartidoDados,
    validar_nascimento_do_candidato,
    validar_nome_de_urna,
    validar_partido,
)
from app.compartilhado.erros import DadosInvalidos

HOJE = date(2026, 11, 25)


@pytest.mark.parametrize("nome_urna", ["Zé", "", "   ", "x" * 31])
def test_recusa_nome_de_urna_fora_de_3_a_30_caracteres(nome_urna):
    """RN-31: nome de urna com menos de 3 ou mais de 30 caracteres (sem as pontas) é recusado."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_nome_de_urna(nome_urna)

    assert erro.value.codigo == "DADOS_INVALIDOS"


@pytest.mark.parametrize("nome_urna", ["Zeca", "x" * 30, "abc"])
def test_aceita_nome_de_urna_de_3_a_30_caracteres(nome_urna):
    """RN-31: os limites 3 e 30 passam."""
    assert validar_nome_de_urna(nome_urna) == nome_urna


def test_nome_de_urna_perde_os_espacos_das_pontas():
    """RN-31: a contagem e o valor devolvido ignoram os espaços nas pontas."""
    assert validar_nome_de_urna("  Carlos Lima ") == "Carlos Lima"


def test_aceita_nascimento_no_passado():
    """RN-31: o dia anterior a hoje já é passado."""
    validar_nascimento_do_candidato(date(2026, 11, 24), HOJE)


@pytest.mark.parametrize("nascimento", [HOJE, date(2027, 1, 1)])
def test_recusa_nascimento_que_nao_esta_no_passado(nascimento):
    """RN-31: nascimento hoje ou no futuro é recusado com `DADOS_INVALIDOS`."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_nascimento_do_candidato(nascimento, HOJE)

    assert erro.value.codigo == "DADOS_INVALIDOS"


def test_partido_valido_vem_normalizado():
    """RN-32: a sigla vira maiúscula e o nome perde os espaços das pontas."""
    dados = validar_partido(
        NovoPartidoDados(sigla=" pino ", nome="  Partido da Inovação ", numero=10)
    )

    assert dados == NovoPartidoDados(sigla="PINO", nome="Partido da Inovação", numero=10)


@pytest.mark.parametrize("sigla", ["A", "ABCDEFGHIJK", "AB-C", "AB CD", ""])
def test_recusa_sigla_fora_do_formato(sigla):
    """RN-32: a sigla tem de 2 a 10 letras ou dígitos."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_partido(NovoPartidoDados(sigla=sigla, nome="Partido", numero=10))

    assert erro.value.codigo == "DADOS_INVALIDOS"


@pytest.mark.parametrize("numero", [9, 100, 0, -10])
def test_recusa_numero_de_partido_fora_de_10_a_99(numero):
    """RN-32: o número do partido fica entre 10 e 99."""
    with pytest.raises(DadosInvalidos):
        validar_partido(NovoPartidoDados(sigla="PINO", nome="Partido", numero=numero))


@pytest.mark.parametrize("numero", [10, 99])
def test_aceita_os_limites_do_numero_de_partido(numero):
    """RN-32: 10 e 99 passam."""
    validar_partido(NovoPartidoDados(sigla="PINO", nome="Partido", numero=numero))


@pytest.mark.parametrize("nome", ["", "   ", "x" * 101])
def test_recusa_nome_de_partido_vazio_ou_longo(nome):
    """RN-32: o nome do partido tem de 1 a 100 caracteres."""
    with pytest.raises(DadosInvalidos):
        validar_partido(NovoPartidoDados(sigla="PINO", nome=nome, numero=10))
