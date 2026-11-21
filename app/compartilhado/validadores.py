"""Validadores puros (sem banco e sem HTTP) usados por vários módulos."""

import re
from datetime import date

FORMATO_CPF = re.compile(r"^[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}$")

# Maior valor de uma coluna BIGINT do PostgreSQL. Um ID maior nem chega ao banco (que daria 500).
MAIOR_ID = 9_223_372_036_854_775_807


def so_digitos(texto: str) -> bool:
    """Diz se o texto tem só dígitos de 0 a 9 (ASCII).

    `str.isdigit()` sozinho aceita dígitos de outros alfabetos (como os arábico-índicos),
    que o banco e o `int()` tratam de outro jeito. Por isso exigimos também `isascii()`.
    """
    return texto.isascii() and texto.isdigit()


def normalizar_cpf(valor: str) -> str:
    """Aceita '529.982.247-25' ou '52998224725' e devolve só os dígitos (RN-07).

    Devolve texto vazio se o formato não for de um CPF (letras, tamanho errado etc.).
    """
    if not FORMATO_CPF.match(valor.strip()):
        return ""
    return re.sub(r"[^0-9]", "", valor)


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores (RN-07).

    Espera o CPF já normalizado (só dígitos). Recusa tamanho errado e dígitos todos iguais.
    """
    if len(cpf) != 11 or not so_digitos(cpf) or cpf == cpf[0] * 11:
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


def sem_caractere_nulo(texto: str | None) -> str | None:
    """Recusa texto com o caractere nulo (\\x00), que o PostgreSQL não aceita em colunas de texto.

    Usado como `AfterValidator` nos esquemas: o pedido vira 422, e não um erro 500 no banco.
    """
    if texto is not None and "\x00" in texto:
        raise ValueError("O texto não pode conter o caractere nulo.")
    return texto
