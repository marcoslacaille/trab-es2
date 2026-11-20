"""Contratos Pydantic de entrada e saída do módulo de candidatos e partidos."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# RN-08 (nome) e RN-31 (nome de urna): tamanhos conferidos sem contar espaços nas pontas.
Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
NomeDeUrna = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=30)]

# RN-32: a sigla chega em qualquer caixa e é convertida para maiúsculas. O padrão aceita as duas
# caixas porque o Pydantic confere o padrão antes de converter.
Sigla = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{2,10}$"),
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

    nome: Nome
    nome_urna: NomeDeUrna = Field(description="Como o candidato aparece na urna (3 a 30).")
    # Só o tamanho é limitado aqui; o formato e os dígitos verificadores são conferidos pelo
    # serviço de identidade, que responde `CPF_INVALIDO` (RN-07).
    cpf: str = Field(max_length=20, description="CPF com ou sem pontuação.")
    data_nascimento: date = Field(description="Precisa estar no passado (RN-31).")
    senha: str = Field(description="De 8 caracteres até 72 bytes. Nunca é devolvida (RN-05).")


class AlteracaoCandidato(BaseModel):
    """O que o Chefe pode mudar num candidato (RN-31). O CPF não muda (RN-33).

    Mandar o CPF (ou qualquer outro campo) dá 422. Campo ausente não muda.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"nome_urna": "Carlos H. Lima", "senha": "NovaSenha@456"}},
    )

    nome: Nome | None = None
    nome_urna: NomeDeUrna | None = None
    data_nascimento: date | None = None
    senha: str | None = Field(default=None, description="Nova senha (RN-05).")


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

    id: int
    nome: str
    nome_urna: str
    cpf: str = Field(description="CPF só com dígitos.")
    data_nascimento: date
    criado_em: datetime = Field(description="Instante do cadastro.")


class NovoPartido(BaseModel):
    """Dados para cadastrar um partido (RN-32). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"sigla": "PINO", "nome": "Partido da Inovação", "numero": 10}
        },
    )

    sigla: Sigla = Field(description="De 2 a 10 letras ou dígitos. Vira maiúscula.")
    nome: str = Field(min_length=1, max_length=100)
    numero: int = Field(ge=10, le=99, description="Número de 2 dígitos, de 10 a 99.")


class PartidoResposta(BaseModel):
    """Um partido."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {"id": 1, "sigla": "PINO", "nome": "Partido da Inovação", "numero": 10}
        },
    )

    id: int
    sigla: str
    nome: str
    numero: int
