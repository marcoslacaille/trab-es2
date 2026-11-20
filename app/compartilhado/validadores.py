"""Validadores puros (sem banco e sem HTTP) usados por vários módulos."""

import re
from datetime import date

FORMATO_CPF = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")


def normalizar_cpf(valor: str) -> str:
    """Aceita '529.982.247-25' ou '52998224725' e devolve só os dígitos (RN-07).

    Devolve texto vazio se o formato não for de um CPF (letras, tamanho errado etc.).
    """
    if not FORMATO_CPF.match(valor.strip()):
        return ""
    return re.sub(r"\D", "", valor)


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores (RN-07).

    Espera o CPF já normalizado (só dígitos). Recusa tamanho errado e dígitos todos iguais.
    """
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def calcular_idade(nascimento: date, referencia: date) -> int:
    """Idade completa, em anos, na data de referência (base da RN-22).

    Quem nasceu em 29/02 só faz aniversário em 01/03 nos anos não bissextos.
    """
    ja_fez_aniversario = (referencia.month, referencia.day) >= (nascimento.month, nascimento.day)
    return referencia.year - nascimento.year - (0 if ja_fez_aniversario else 1)
