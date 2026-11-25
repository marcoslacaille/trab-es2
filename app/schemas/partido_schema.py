"""Schemas de partido: o JSON de entrada e saída da API."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.validadores import sem_caractere_nulo

# RN-32: a sigla chega em qualquer caixa e é convertida para maiúsculas. O padrão aceita as duas
# caixas porque o Pydantic confere o padrão antes de converter.
Sigla = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{2,10}$"),
]


class NovoPartido(BaseModel):
    """Dados para cadastrar um partido (RN-32). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"sigla": "PINO", "nome": "Partido da Inovação", "numero": 10}
        },
    )

    sigla: Sigla = Field(
        description="De 2 a 10 letras ou dígitos. Vira maiúscula.", examples=["PINO"]
    )
    nome: Annotated[str, AfterValidator(sem_caractere_nulo)] = Field(
        min_length=1,
        max_length=100,
        description="Nome do partido.",
        examples=["Partido da Inovação"],
    )
    numero: int = Field(ge=10, le=99, description="Número de 2 dígitos, de 10 a 99.", examples=[10])


class PartidoResposta(BaseModel):
    """Um partido."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {"id": 1, "sigla": "PINO", "nome": "Partido da Inovação", "numero": 10}
        },
    )

    id: int = Field(description="Identificador do partido.", examples=[1])
    sigla: str = Field(description="Sigla em maiúsculas.", examples=["PINO"])
    nome: str = Field(description="Nome do partido.", examples=["Partido da Inovação"])
    numero: int = Field(description="Número de 2 dígitos.", examples=[10])
