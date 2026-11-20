"""Regras puras de candidatos e partidos: dados que o serviço devolve e recebe, e validações."""

import re
from dataclasses import dataclass

from app.compartilhado.erros import DadosInvalidos

FORMATO_SIGLA = re.compile(r"^[A-Z0-9]{2,10}$")
NOME_MAXIMO_DO_PARTIDO = 100
NUMERO_MINIMO_DO_PARTIDO = 10
NUMERO_MAXIMO_DO_PARTIDO = 99


@dataclass(frozen=True)
class PartidoResumo:
    """Um partido como os outros módulos o enxergam (a candidatura guarda o `id`)."""

    id: int
    sigla: str
    nome: str
    numero: int


@dataclass(frozen=True)
class NovoPartidoDados:
    """Tudo o que o Chefe informa para cadastrar um partido (RN-32)."""

    sigla: str
    nome: str
    numero: int


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
