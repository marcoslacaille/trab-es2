"""Contratos Pydantic de entrada e saída do módulo de eleitores, com exemplos para o Swagger."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# RN-08: de 3 a 120 caracteres, ignorando espaços nas pontas.
Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]


class NovoEleitor(BaseModel):
    """Dados para cadastrar um eleitor (RN-20). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nome": "Ana Beatriz Souza",
                "cpf": "011.524.493-03",
                "titulo_eleitor": "100000000001",
                "data_nascimento": "1990-04-12",
                "senha": "Eleitor@123",
            }
        },
    )

    nome: Nome
    # Só o tamanho é limitado aqui; o formato e os dígitos verificadores são conferidos pelo
    # serviço de identidade, que responde `CPF_INVALIDO` (RN-07).
    cpf: str = Field(max_length=20, description="CPF com ou sem pontuação.")
    titulo_eleitor: str = Field(
        pattern=r"^[0-9]{12}$", description="Título com 12 dígitos (RN-21)."
    )
    data_nascimento: date = Field(description="O eleitor precisa ter 16 anos completos (RN-22).")
    senha: str = Field(description="De 8 caracteres até 72 bytes. Nunca é devolvida (RN-05).")


class AlteracaoEleitor(BaseModel):
    """O que o Chefe pode mudar num eleitor: nome, data de nascimento e senha (RN-23).

    CPF e título não mudam: mandá-los (ou qualquer outro campo) dá 422. Campo ausente não muda.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"nome": "Ana Beatriz Souza Lima", "senha": "NovaSenha@456"}},
    )

    nome: Nome | None = None
    data_nascimento: date | None = None
    senha: str | None = Field(default=None, description="Nova senha (RN-05).")


class EleitorResposta(BaseModel):
    """Um eleitor, sem a senha."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Ana Beatriz Souza",
                "cpf": "01152449303",
                "titulo_eleitor": "100000000001",
                "data_nascimento": "1990-04-12",
                "criado_em": "2026-11-25T07:30:00-03:00",
            }
        },
    )

    id: int
    nome: str
    cpf: str = Field(description="CPF só com dígitos.")
    titulo_eleitor: str
    data_nascimento: date
    criado_em: datetime = Field(description="Instante do cadastro.")
