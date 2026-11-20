"""Contratos Pydantic de entrada e saída do módulo de eleições."""

from datetime import date, datetime, time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.compartilhado.dominio import Cargo
from app.eleicoes.dominio import (
    CandidaturaDetalhada,
    EleicaoResumo,
    StatusEleicao,
    links_da_eleicao,
)


def _sem_fuso(horario: time) -> time:
    """Horário de urna é de parede: com fuso (ex.: `08:00-03:00`) não dá para comparar."""
    if horario.tzinfo is not None:
        raise ValueError("Informe o horário sem fuso, por exemplo 08:00.")
    return horario


Horario = Annotated[time, AfterValidator(_sem_fuso)]
Descricao = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


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

    descricao: Descricao = Field(description="Nome do pleito (1 a 120 caracteres).")
    data: date = Field(description="Dia da eleição; não pode ser anterior a hoje.")
    turno: int = Field(ge=1, le=2, description="1 ou 2. Cada turno é uma eleição separada.")
    horario_abertura: Horario = Field(description="Início da janela de votação.")
    horario_encerramento: Horario = Field(
        description="Fim da janela; depois do horário de abertura."
    )


class AlteracaoEleicao(BaseModel):
    """O que o Chefe pode mudar numa eleição AGENDADA (RN-14). Campo ausente não muda."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"horario_encerramento": "18:00"}},
    )

    descricao: Descricao | None = None
    data: date | None = None
    turno: int | None = Field(default=None, ge=1, le=2)
    horario_abertura: Horario | None = None
    horario_encerramento: Horario | None = None


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

    id: int
    descricao: str
    data: date
    turno: int
    horario_abertura: time
    horario_encerramento: time
    status: StatusEleicao
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

Numero = Annotated[str, Field(max_length=20, description="Só dígitos, na quantidade do cargo.")]


class NovaCandidatura(BaseModel):
    """Dados para criar uma candidatura (RN-40). Campos desconhecidos são recusados."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"candidato_id": 1, "partido_id": 1, "cargo": "PRESIDENTE", "numero": "10"}
        },
    )

    candidato_id: int = Field(gt=0, description="Candidato que disputa (RN-46: precisa existir).")
    partido_id: int = Field(gt=0, description="Partido pelo qual disputa (RN-46: precisa existir).")
    cargo: Cargo = Field(description="Um dos 5 cargos (RN-41).")
    numero: Numero


class AlteracaoCandidatura(BaseModel):
    """O que pode mudar numa candidatura: cargo, número e partido. Candidato e eleição, não."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"numero": "11"}})

    cargo: Cargo | None = None
    numero: Numero | None = None
    partido_id: int | None = Field(default=None, gt=0)


class CandidatoDaCandidatura(BaseModel):
    """Candidato como aparece na candidatura."""

    id: int
    nome_urna: str


class PartidoDaCandidatura(BaseModel):
    """Partido como aparece na candidatura."""

    id: int
    sigla: str
    numero: int


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

    id: int
    eleicao_id: int
    cargo: Cargo
    numero: str
    candidato: CandidatoDaCandidatura
    partido: PartidoDaCandidatura

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
