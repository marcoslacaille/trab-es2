"""Regras puras de candidatos e partidos: validações, sem banco."""

import re
from datetime import date

from app.core.exceptions import DadosInvalidos
from app.dto.partido_dto import NovoPartidoDados

FORMATO_SIGLA = re.compile(r"^[A-Z0-9]{2,10}$")
NOME_MAXIMO_DO_PARTIDO = 100
NUMERO_MINIMO_DO_PARTIDO = 10
NUMERO_MAXIMO_DO_PARTIDO = 99
NOME_DE_URNA_MINIMO = 3
NOME_DE_URNA_MAXIMO = 30


def validar_partido(dados: NovoPartidoDados) -> NovoPartidoDados:
    """RN-32: confere os dados do partido e devolve-os normalizados.

    A sigla vira maiúscula e deve ter de 2 a 10 letras ou dígitos; o nome, sem espaços nas
    pontas, não pode ser vazio nem passar de 100 caracteres; o número fica entre 10 e 99.
    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se algo estiver errado.
    """
    sigla = dados.sigla.strip().upper()
    nome = dados.nome.strip()
    if not FORMATO_SIGLA.fullmatch(sigla):
        raise DadosInvalidos(
            "A sigla deve ter de 2 a 10 letras ou dígitos.", codigo="DADOS_INVALIDOS"
        )
    if not nome or len(nome) > NOME_MAXIMO_DO_PARTIDO:
        raise DadosInvalidos(
            f"O nome do partido deve ter de 1 a {NOME_MAXIMO_DO_PARTIDO} caracteres.",
            codigo="DADOS_INVALIDOS",
        )
    if not NUMERO_MINIMO_DO_PARTIDO <= dados.numero <= NUMERO_MAXIMO_DO_PARTIDO:
        raise DadosInvalidos(
            f"O número do partido deve ficar entre {NUMERO_MINIMO_DO_PARTIDO} e "
            f"{NUMERO_MAXIMO_DO_PARTIDO}.",
            codigo="DADOS_INVALIDOS",
        )
    return NovoPartidoDados(sigla=sigla, nome=nome, numero=dados.numero)


def validar_nome_de_urna(nome_urna: str) -> str:
    """RN-31: o nome de urna tem de 3 a 30 caracteres, sem contar espaços nas pontas.

    Devolve o nome sem os espaços das pontas. Levanta `DadosInvalidos` com o código
    `DADOS_INVALIDOS` (422) se o tamanho não servir.
    """
    nome_urna = nome_urna.strip()
    if not NOME_DE_URNA_MINIMO <= len(nome_urna) <= NOME_DE_URNA_MAXIMO:
        raise DadosInvalidos(
            f"O nome de urna deve ter de {NOME_DE_URNA_MINIMO} a {NOME_DE_URNA_MAXIMO} caracteres.",
            codigo="DADOS_INVALIDOS",
        )
    return nome_urna


def validar_nascimento_do_candidato(data_nascimento: date, hoje: date) -> None:
    """RN-31: a data de nascimento do candidato precisa estar no passado.

    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se for hoje ou futura.
    """
    if data_nascimento >= hoje:
        raise DadosInvalidos(
            "A data de nascimento deve estar no passado.", codigo="DADOS_INVALIDOS"
        )
