"""Schemas de eleitores: o JSON de entrada e saída, com exemplos para o Swagger."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.validadores import sem_caractere_nulo

# RN-08: de 3 a 120 caracteres, ignorando espaços nas pontas.
Nome = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=120),
    AfterValidator(sem_caractere_nulo),
]


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

    nome: Nome = Field(
        description="Nome completo (3 a 120 caracteres).", examples=["Ana Beatriz Souza"]
    )
    # Só o tamanho é limitado aqui; o formato e os dígitos verificadores são conferidos pelo
    # serviço de identidade, que responde `CPF_INVALIDO` (RN-07).
    cpf: str = Field(
        max_length=20, description="CPF com ou sem pontuação.", examples=["011.524.493-03"]
    )
    titulo_eleitor: str = Field(
        pattern=r"^[0-9]{12}$",
        description="Título com 12 dígitos (RN-21).",
        examples=["100000000001"],
    )
    data_nascimento: date = Field(
        description="O eleitor precisa ter 16 anos completos (RN-22).", examples=["1990-04-12"]
    )
    senha: str = Field(
        description="De 8 caracteres até 72 bytes. Nunca é devolvida (RN-05).",
        examples=["Eleitor@123"],
    )


class AlteracaoEleitor(BaseModel):
    """O que o Chefe pode mudar num eleitor: nome, data de nascimento e senha (RN-23).

    CPF e título não mudam: mandá-los (ou qualquer outro campo) dá 422. Campo ausente não muda.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"nome": "Ana Beatriz Souza Lima", "senha": "NovaSenha@456"}},
    )

    nome: Nome | None = Field(default=None, examples=["Ana Beatriz Souza Lima"])
    data_nascimento: date | None = Field(default=None, examples=["1990-04-12"])
    senha: str | None = Field(
        default=None, description="Nova senha (RN-05).", examples=["NovaSenha@456"]
    )


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

    id: int = Field(description="Identificador do eleitor.", examples=[1])
    nome: str = Field(description="Nome completo.", examples=["Ana Beatriz Souza"])
    cpf: str = Field(description="CPF só com dígitos.", examples=["01152449303"])
    titulo_eleitor: str = Field(description="Título com 12 dígitos.", examples=["100000000001"])
    data_nascimento: date = Field(description="Data de nascimento.", examples=["1990-04-12"])
    criado_em: datetime = Field(description="Instante do cadastro.")
