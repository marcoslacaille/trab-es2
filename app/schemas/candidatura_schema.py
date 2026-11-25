"""Schemas de candidatura: o JSON de entrada e saída da API."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.validadores import MAIOR_ID
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.models.enums import Cargo

Numero = Annotated[
    str, Field(max_length=20, description="Só dígitos, na quantidade do cargo.", examples=["10"])
]


class NovaCandidatura(BaseModel):
    """Dados para criar uma candidatura (RN-40). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"candidato_id": 1, "partido_id": 1, "cargo": "PRESIDENTE", "numero": "10"}
        },
    )

    candidato_id: int = Field(
        gt=0, le=MAIOR_ID, description="Candidato que disputa (RN-46: precisa existir)."
    )
    partido_id: int = Field(
        gt=0, le=MAIOR_ID, description="Partido pelo qual disputa (RN-46: precisa existir)."
    )
    cargo: Cargo = Field(description="Um dos 5 cargos (RN-41).")
    numero: Numero


class AlteracaoCandidatura(BaseModel):
    """O que pode mudar numa candidatura: cargo, número e partido. Candidato e eleição, não."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"numero": "11"}})

    cargo: Cargo | None = Field(default=None, examples=["PRESIDENTE"])
    numero: Numero | None = Field(default=None, examples=["11"])
    partido_id: int | None = Field(default=None, gt=0, le=MAIOR_ID, examples=[1])


class CandidatoDaCandidatura(BaseModel):
    """Candidato como aparece na candidatura."""

    id: int = Field(description="Identificador do candidato.", examples=[1])
    nome_urna: str = Field(description="Nome de urna.", examples=["Carlos Lima"])


class PartidoDaCandidatura(BaseModel):
    """Partido como aparece na candidatura."""

    id: int = Field(description="Identificador do partido.", examples=[1])
    sigla: str = Field(description="Sigla do partido.", examples=["PINO"])
    numero: int = Field(description="Número do partido.", examples=[10])


class CandidaturaResposta(BaseModel):
    """Uma candidatura com os dados de exibição do candidato e do partido."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "eleicao_id": 1,
                "cargo": "PRESIDENTE",
                "numero": "10",
                "candidato": {"id": 1, "nome_urna": "Carlos Lima"},
                "partido": {"id": 1, "sigla": "PINO", "numero": 10},
            }
        }
    )

    id: int = Field(description="Identificador da candidatura.", examples=[1])
    eleicao_id: int = Field(description="Eleição em que disputa.", examples=[1])
    cargo: Cargo = Field(description="Cargo disputado.", examples=["PRESIDENTE"])
    numero: str = Field(description="Número do candidato no cargo.", examples=["10"])
    candidato: CandidatoDaCandidatura = Field(description="Dados de exibição do candidato.")
    partido: PartidoDaCandidatura = Field(description="Dados de exibição do partido.")

    @classmethod
    def de_candidatura(cls, candidatura: CandidaturaDetalhada) -> "CandidaturaResposta":
        """Monta a resposta a partir da candidatura detalhada do serviço."""
        return cls(
            id=candidatura.id,
            eleicao_id=candidatura.eleicao_id,
            cargo=candidatura.cargo,
            numero=candidatura.numero,
            candidato=CandidatoDaCandidatura(
                id=candidatura.candidato_id, nome_urna=candidatura.nome_urna
            ),
            partido=PartidoDaCandidatura(
                id=candidatura.partido_id,
                sigla=candidatura.partido_sigla,
                numero=candidatura.partido_numero,
            ),
        )
