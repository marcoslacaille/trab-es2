"""Contratos Pydantic de entrada e saída do módulo de eleições."""

from datetime import date, datetime, time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.eleicoes.dominio import EleicaoResumo, StatusEleicao, links_da_eleicao


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
