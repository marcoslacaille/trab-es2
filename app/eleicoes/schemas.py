"""Schemas de eleições e candidaturas: o JSON de entrada e saída (contratos Pydantic)."""

from datetime import date, datetime, time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.validadores import MAIOR_ID, sem_caractere_nulo
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.eleicoes.dominio import links_da_eleicao
from app.models.enums import Cargo, StatusEleicao


def _sem_fuso(horario: time) -> time:
    """Horário de urna é de parede: com fuso (ex.: `08:00-03:00`) não dá para comparar."""
    if horario.tzinfo is not None:
        raise ValueError("Informe o horário sem fuso, por exemplo 08:00.")
    return horario


Horario = Annotated[time, AfterValidator(_sem_fuso)]
Descricao = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    AfterValidator(sem_caractere_nulo),
]


class NovaEleicao(BaseModel):
    """Dados para agendar uma eleição (RN-11). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "descricao": "Eleições Gerais 2026 — 1º turno",
                "data": "2026-11-25",
                "turno": 1,
                "horario_abertura": "08:00",
                "horario_encerramento": "17:00",
            }
        },
    )

    descricao: Descricao = Field(
        description="Nome do pleito (1 a 120 caracteres).",
        examples=["Eleições Gerais 2026 — 1º turno"],
    )
    data: date = Field(
        description="Dia da eleição; não pode ser anterior a hoje.", examples=["2026-11-25"]
    )
    turno: int = Field(
        ge=1, le=2, description="1 ou 2. Cada turno é uma eleição separada.", examples=[1]
    )
    horario_abertura: Horario = Field(
        description="Início da janela de votação.", examples=["08:00"]
    )
    horario_encerramento: Horario = Field(
        description="Fim da janela; depois do horário de abertura.", examples=["17:00"]
    )


class AlteracaoEleicao(BaseModel):
    """O que o Chefe pode mudar numa eleição AGENDADA (RN-14). Campo ausente não muda."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"horario_encerramento": "18:00"}},
    )

    descricao: Descricao | None = Field(default=None, examples=["Eleições Gerais 2026 — 1º turno"])
    data: date | None = Field(default=None, examples=["2026-11-25"])
    turno: int | None = Field(default=None, ge=1, le=2, examples=[1])
    horario_abertura: Horario | None = Field(default=None, examples=["08:00"])
    horario_encerramento: Horario | None = Field(default=None, examples=["17:00"])


class LinkResposta(BaseModel):
    """Uma ação possível sobre a eleição (HATEOAS)."""

    rel: str = Field(description="Nome da ação, por exemplo `abrir`.")
    metodo: str = Field(description="Método HTTP.")
    href: str = Field(description="Caminho da ação.")


class EleicaoResposta(BaseModel):
    """Uma eleição, com situação, janela e carimbos de tempo."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "descricao": "Eleições Gerais 2026 — 1º turno",
                "data": "2026-11-25",
                "turno": 1,
                "horario_abertura": "08:00:00",
                "horario_encerramento": "17:00:00",
                "status": "AGENDADA",
                "aberta_em": None,
                "encerrada_em": None,
                "links": [
                    {"rel": "self", "metodo": "GET", "href": "/api/v1/eleicoes/1"},
                    {"rel": "editar", "metodo": "PATCH", "href": "/api/v1/eleicoes/1"},
                    {
                        "rel": "candidaturas",
                        "metodo": "GET",
                        "href": "/api/v1/eleicoes/1/candidaturas",
                    },
                    {
                        "rel": "nova-candidatura",
                        "metodo": "POST",
                        "href": "/api/v1/eleicoes/1/candidaturas",
                    },
                    {"rel": "abrir", "metodo": "POST", "href": "/api/v1/eleicoes/1/abertura"},
                ],
            }
        },
    )

    id: int = Field(description="Identificador da eleição.", examples=[1])
    descricao: str = Field(
        description="Nome do pleito.", examples=["Eleições Gerais 2026 — 1º turno"]
    )
    data: date = Field(description="Dia da eleição.", examples=["2026-11-25"])
    turno: int = Field(description="1 ou 2.", examples=[1])
    horario_abertura: time = Field(
        description="Início da janela de votação.", examples=["08:00:00"]
    )
    horario_encerramento: time = Field(
        description="Fim da janela de votação.", examples=["17:00:00"]
    )
    status: StatusEleicao = Field(
        description="AGENDADA, ABERTA ou ENCERRADA.", examples=["AGENDADA"]
    )
    aberta_em: datetime | None = Field(description="Instante da abertura; nulo até abrir.")
    encerrada_em: datetime | None = Field(
        description="Instante do encerramento; nulo até encerrar."
    )
    links: list[LinkResposta] = Field(
        description="Ações possíveis para o seu perfil neste status da eleição (RN-19)."
    )

    @classmethod
    def de_eleicao(cls, eleicao: EleicaoResumo, perfil: str) -> "EleicaoResposta":
        """Monta a resposta com os `links` que o perfil pode seguir (RN-19)."""
        return cls(
            id=eleicao.id,
            descricao=eleicao.descricao,
            data=eleicao.data,
            turno=eleicao.turno,
            horario_abertura=eleicao.horario_abertura,
            horario_encerramento=eleicao.horario_encerramento,
            status=eleicao.status,
            aberta_em=eleicao.aberta_em,
            encerrada_em=eleicao.encerrada_em,
            links=[
                LinkResposta(rel=link.rel, metodo=link.metodo, href=link.href)
                for link in links_da_eleicao(eleicao, perfil)
            ],
        )


# ---------------------------------------------------------------- candidaturas

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
