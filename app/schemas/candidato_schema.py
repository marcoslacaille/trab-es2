"""Schemas de candidato: o JSON de entrada e saída da API."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.validadores import sem_caractere_nulo

# RN-08 (nome) e RN-31 (nome de urna): tamanhos conferidos sem contar espaços nas pontas.
Nome = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=120),
    AfterValidator(sem_caractere_nulo),
]
NomeDeUrna = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=30),
    AfterValidator(sem_caractere_nulo),
]


class NovoCandidato(BaseModel):
    """Dados para cadastrar um candidato (RN-31). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nome": "Carlos Henrique Lima",
                "nome_urna": "Carlos Lima",
                "cpf": "398.259.791-94",
                "data_nascimento": "1968-03-05",
                "senha": "Candidato@123",
            }
        },
    )

    nome: Nome = Field(description="Nome completo (3 a 120).", examples=["Carlos Henrique Lima"])
    nome_urna: NomeDeUrna = Field(
        description="Como o candidato aparece na urna (3 a 30).", examples=["Carlos Lima"]
    )
    # Só o tamanho é limitado aqui; o formato e os dígitos verificadores são conferidos pelo
    # `UsuarioService`, que responde `CPF_INVALIDO` (RN-07).
    cpf: str = Field(
        max_length=20, description="CPF com ou sem pontuação.", examples=["398.259.791-94"]
    )
    data_nascimento: date = Field(
        description="Precisa estar no passado (RN-31).", examples=["1968-03-05"]
    )
    senha: str = Field(
        description="De 8 caracteres até 72 bytes. Nunca é devolvida (RN-05).",
        examples=["Candidato@123"],
    )


class AlteracaoCandidato(BaseModel):
    """O que o Chefe pode mudar num candidato (RN-31). O CPF não muda (RN-33).

    Mandar o CPF (ou qualquer outro campo) dá 422. Campo ausente não muda.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"nome_urna": "Carlos H. Lima", "senha": "NovaSenha@456"}},
    )

    nome: Nome | None = Field(default=None, examples=["Carlos Henrique Lima"])
    nome_urna: NomeDeUrna | None = Field(default=None, examples=["Carlos H. Lima"])
    data_nascimento: date | None = Field(default=None, examples=["1968-03-05"])
    senha: str | None = Field(
        default=None, description="Nova senha (RN-05).", examples=["NovaSenha@456"]
    )


class CandidatoResposta(BaseModel):
    """Um candidato, sem a senha."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Carlos Henrique Lima",
                "nome_urna": "Carlos Lima",
                "cpf": "39825979194",
                "data_nascimento": "1968-03-05",
                "criado_em": "2026-11-25T07:30:00-03:00",
            }
        },
    )

    id: int = Field(description="Identificador do candidato.", examples=[1])
    nome: str = Field(description="Nome completo.", examples=["Carlos Henrique Lima"])
    nome_urna: str = Field(description="Nome que aparece na urna.", examples=["Carlos Lima"])
    cpf: str = Field(description="CPF só com dígitos.", examples=["39825979194"])
    data_nascimento: date = Field(description="Data de nascimento.", examples=["1968-03-05"])
    criado_em: datetime = Field(description="Instante do cadastro.")
