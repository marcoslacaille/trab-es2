"""Contratos Pydantic de entrada e saída da votação, com exemplos para o Swagger."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.compartilhado.dominio import Cargo
from app.votacao.dominio import (
    CandidatoDaCedula,
    CedulaDoEleitor,
    ComprovanteVoto,
    ModoEscolha,
    Participacao,
    PreviaVoto,
    TipoVoto,
)


class LinkDaVotacao(BaseModel):
    """Uma ação possível a seguir (HATEOAS)."""

    rel: str = Field(description="Nome da ação, por exemplo `confirmar`.")
    metodo: str = Field(description="Método HTTP.")
    href: str = Field(description="Caminho da ação.")


class CandidatoNaCedula(BaseModel):
    """Candidato como o eleitor o vê na cédula."""

    numero: str = Field(description="Número do candidato no cargo.", examples=["10"])
    nome_urna: str = Field(description="Nome de urna.", examples=["Carlos Lima"])
    partido_sigla: str = Field(description="Sigla do partido.", examples=["PINO"])

    @classmethod
    def de_candidato(cls, candidato: CandidatoDaCedula) -> "CandidatoNaCedula":
        return cls(
            numero=candidato.numero,
            nome_urna=candidato.nome_urna,
            partido_sigla=candidato.partido_sigla,
        )


class CargoNaCedula(BaseModel):
    """Um cargo disputado, com os dígitos do número e os candidatos."""

    cargo: Cargo = Field(description="Cargo da cédula.", examples=["PRESIDENTE"])
    digitos: int = Field(description="Quantidade de dígitos do número neste cargo (RN-42).")
    ja_votou: bool = Field(description="O eleitor já votou neste cargo? (RN-61).")
    candidatos: list[CandidatoNaCedula] = Field(description="Candidatos do cargo.")


class CedulaResposta(BaseModel):
    """A cédula do eleitor: só os cargos disputados, na ordem da urna (RN-55)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eleicao_id": 1,
                "cargos": [
                    {
                        "cargo": "PRESIDENTE",
                        "digitos": 2,
                        "ja_votou": False,
                        "candidatos": [
                            {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO"},
                            {"numero": "20", "nome_urna": "Marina Costa", "partido_sigla": "UC"},
                        ],
                    }
                ],
            }
        }
    )

    eleicao_id: int = Field(description="Eleição da cédula.", examples=[1])
    cargos: list[CargoNaCedula] = Field(description="Um bloco por cargo.")

    @classmethod
    def de_cedula(cls, cedula: CedulaDoEleitor) -> "CedulaResposta":
        return cls(
            eleicao_id=cedula.eleicao_id,
            cargos=[
                CargoNaCedula(
                    cargo=c.cargo,
                    digitos=c.digitos,
                    ja_votou=c.ja_votou,
                    candidatos=[CandidatoNaCedula.de_candidato(x) for x in c.candidatos],
                )
                for c in cedula.cargos
            ],
        )


class PedidoRegistroVoto(BaseModel):
    """Etapa 1 do voto (RN-56, RN-58). Campos desconhecidos são recusados.

    No modo NUMERO o `numero` é obrigatório; no modo BRANCO é proibido. A quantidade exata de
    dígitos do cargo é conferida pelo serviço (`NUMERO_INVALIDO_PARA_CARGO`).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"cargo": "PRESIDENTE", "modo": "NUMERO", "numero": "10"}},
    )

    cargo: Cargo = Field(description="Cargo em que vota.", examples=["PRESIDENTE"])
    modo: ModoEscolha = Field(
        description="NUMERO (digita o número) ou BRANCO.", examples=["NUMERO"]
    )
    numero: str | None = Field(
        default=None,
        pattern=r"^[0-9]{1,5}$",
        description="Só dígitos (1 a 5). Obrigatório no modo NUMERO, proibido no modo BRANCO.",
    )

    @model_validator(mode="after")
    def _numero_conforme_o_modo(self) -> Self:
        if self.modo == ModoEscolha.NUMERO and self.numero is None:
            raise ValueError("O número é obrigatório no modo NUMERO.")
        if self.modo == ModoEscolha.BRANCO and self.numero is not None:
            raise ValueError("O número não deve ser informado no modo BRANCO.")
        return self


class PreviaVotoResposta(BaseModel):
    """A prévia do voto: nada foi gravado. O `token_cedula` serve para confirmar (RN-56, RN-57)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cargo": "PRESIDENTE",
                "tipo_voto": "NOMINAL",
                "candidato": {"numero": "10", "nome_urna": "Carlos Lima", "partido_sigla": "PINO"},
                "mensagem": "Confira os dados e confirme o voto.",
                "token_cedula": "gAAAAABpQ2...",
                "expira_em": "2026-11-25T10:05:00-03:00",
                "links": [
                    {
                        "rel": "confirmar",
                        "metodo": "POST",
                        "href": "/api/v1/votacao/eleicoes/1/votos/confirmacao",
                    }
                ],
            }
        }
    )

    cargo: Cargo = Field(description="Cargo do voto.", examples=["PRESIDENTE"])
    tipo_voto: TipoVoto = Field(description="NOMINAL, BRANCO ou NULO.", examples=["NOMINAL"])
    candidato: CandidatoNaCedula | None = Field(description="Nulo nos votos BRANCO e NULO.")
    mensagem: str = Field(description="Texto para o eleitor conferir.")
    token_cedula: str = Field(
        description="Cédula cifrada (opaca), válida por 5 minutos (RN-57, RN-60)."
    )
    expira_em: datetime = Field(description="Instante em que o token_cedula expira.")
    links: list[LinkDaVotacao] = Field(description="Próximas ações possíveis.")

    @classmethod
    def de_previa(cls, previa: PreviaVoto) -> "PreviaVotoResposta":
        return cls(
            cargo=previa.cargo,
            tipo_voto=previa.tipo,
            candidato=(
                CandidatoNaCedula.de_candidato(previa.candidato) if previa.candidato else None
            ),
            mensagem=previa.mensagem,
            token_cedula=previa.token_cedula,
            expira_em=previa.expira_em,
            links=[
                LinkDaVotacao(
                    rel="confirmar",
                    metodo="POST",
                    href=f"/api/v1/votacao/eleicoes/{previa.eleicao_id}/votos/confirmacao",
                )
            ],
        )


class PedidoConfirmacaoVoto(BaseModel):
    """Etapa 2 do voto: a cédula recebida no registro."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"token_cedula": "eyJhbGciOiJIUzI1NiIs..."}}
    )

    token_cedula: str = Field(
        min_length=1,
        max_length=2000,
        description="Token recebido no registro do voto.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )


class ComprovanteVotoResposta(BaseModel):
    """Voto confirmado. Não contém a escolha (RN-60)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eleicao_id": 1,
                "cargo": "PRESIDENTE",
                "mensagem": "Voto confirmado.",
                "links": [
                    {"rel": "cedula", "metodo": "GET", "href": "/api/v1/votacao/eleicoes/1/cedula"},
                    {
                        "rel": "participacao",
                        "metodo": "GET",
                        "href": "/api/v1/votacao/eleicoes/1/participacao",
                    },
                ],
            }
        }
    )

    eleicao_id: int = Field(description="Eleição do voto.", examples=[1])
    cargo: Cargo = Field(description="Cargo em que o voto foi confirmado.", examples=["PRESIDENTE"])
    mensagem: str = Field(description="Confirmação para o eleitor.")
    links: list[LinkDaVotacao] = Field(description="Próximas ações possíveis.")

    @classmethod
    def de_comprovante(cls, comprovante: ComprovanteVoto) -> "ComprovanteVotoResposta":
        base = f"/api/v1/votacao/eleicoes/{comprovante.eleicao_id}"
        return cls(
            eleicao_id=comprovante.eleicao_id,
            cargo=comprovante.cargo,
            mensagem=comprovante.mensagem,
            links=[
                LinkDaVotacao(rel="cedula", metodo="GET", href=f"{base}/cedula"),
                LinkDaVotacao(rel="participacao", metodo="GET", href=f"{base}/participacao"),
            ],
        )


class CargoNaParticipacao(BaseModel):
    """Se o eleitor já votou neste cargo. Nunca diz em quem."""

    cargo: Cargo = Field(description="Cargo.", examples=["PRESIDENTE"])
    ja_votou: bool = Field(description="O eleitor já votou neste cargo? (RN-61).")


class ParticipacaoResposta(BaseModel):
    """Em quais cargos o eleitor já votou nesta eleição (RN-61)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eleicao_id": 1,
                "cargos": [
                    {"cargo": "PRESIDENTE", "ja_votou": True},
                    {"cargo": "SENADOR", "ja_votou": False},
                ],
            }
        }
    )

    eleicao_id: int = Field(description="Eleição consultada.", examples=[1])
    cargos: list[CargoNaParticipacao] = Field(description="Participação por cargo.")

    @classmethod
    def de_participacao(cls, participacao: Participacao) -> "ParticipacaoResposta":
        return cls(
            eleicao_id=participacao.eleicao_id,
            cargos=[
                CargoNaParticipacao(cargo=c.cargo, ja_votou=c.ja_votou) for c in participacao.cargos
            ],
        )
