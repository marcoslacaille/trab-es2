"""Contratos Pydantic de entrada e saída do módulo de candidatos e partidos."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
