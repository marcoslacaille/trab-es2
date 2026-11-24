"""Schemas da apuração (seção 10): o JSON de resposta. Sem data de nascimento (RN-77)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.apuracao.dominio import (
    Apuracao,
    LinhaApuracao,
    ResultadoCargo,
    SituacaoCargo,
    StatusEleicao,
)
from app.compartilhado.dominio import Cargo

_EXEMPLO = {
    "eleicao_id": 1,
    "tipo": "PARCIAL",
    "status_eleicao": "ABERTA",
    "gerado_em": "2026-11-25T10:30:00-03:00",
    "comparecimento": {"eleitores_aptos": 6, "votantes": 3, "abstencao": 3},
    "cargos": [
        {
            "cargo": "PRESIDENTE",
            "total_votos": 3,
            "votos_validos": 2,
            "brancos": 1,
            "nulos": 0,
            "situacao": "DEFINIDO",
            "criterio": "MAIOR_VOTACAO",
            "mais_votado": {
                "numero": "10",
                "nome_urna": "Carlos Lima",
                "partido_sigla": "PINO",
                "votos": 2,
                "percentual_validos": "100.00",
            },
            "candidatos": [
                {
                    "numero": "10",
                    "nome_urna": "Carlos Lima",
                    "partido_sigla": "PINO",
                    "votos": 2,
                    "percentual_validos": "100.00",
                },
                {
                    "numero": "20",
                    "nome_urna": "Marina Costa",
                    "partido_sigla": "UC",
                    "votos": 0,
                    "percentual_validos": "0.00",
                },
            ],
        }
    ],
}


class LinhaApuracaoResposta(BaseModel):
    """Um candidato na apuração do cargo."""

    numero: str = Field(description="Número do candidato no cargo.", examples=["10"])
    nome_urna: str = Field(description="Nome de urna.", examples=["Carlos Lima"])
    partido_sigla: str = Field(description="Sigla do partido.", examples=["PINO"])
    votos: int = Field(description="Votos nominais recebidos.", examples=[2])
    percentual_validos: str = Field(description="Percentual sobre os votos válidos, 2 casas.")

    @classmethod
    def de_linha(cls, linha: LinhaApuracao) -> "LinhaApuracaoResposta":
        return cls(
            numero=linha.numero,
            nome_urna=linha.nome_urna,
            partido_sigla=linha.partido_sigla,
            votos=linha.votos,
            percentual_validos=f"{linha.percentual_validos:.2f}",
        )


class ResultadoCargoResposta(BaseModel):
    """A apuração de um cargo, com todos os candidatos (inclusive com 0 votos)."""

    cargo: Cargo = Field(description="Cargo apurado.", examples=["PRESIDENTE"])
    total_votos: int = Field(description="Votos válidos, brancos e nulos.", examples=[4])
    votos_validos: int = Field(description="Só os votos nominais (RN-76).")
    brancos: int = Field(description="Votos em branco (RN-76).", examples=[1])
    nulos: int = Field(description="Votos nulos (RN-76).", examples=[0])
    situacao: SituacaoCargo = Field(description="Situação da apuração do cargo.")
    criterio: str | None = Field(description="`MAIOR_VOTACAO` ou `DESEMPATE_POR_IDADE`.")
    mais_votado: LinhaApuracaoResposta | None = Field(
        description="Na parcial, quem lidera até agora. Nulo em EMPATE e SEM_VOTOS_VALIDOS."
    )
    candidatos: list[LinhaApuracaoResposta] = Field(
        description="Todos os candidatos, do mais votado ao menos."
    )

    @classmethod
    def de_resultado(cls, resultado: ResultadoCargo) -> "ResultadoCargoResposta":
        mais_votado = resultado.mais_votado
        return cls(
            cargo=resultado.cargo,
            total_votos=resultado.total_votos,
            votos_validos=resultado.votos_validos,
            brancos=resultado.brancos,
            nulos=resultado.nulos,
            situacao=resultado.situacao,
            criterio=resultado.criterio,
            mais_votado=LinhaApuracaoResposta.de_linha(mais_votado) if mais_votado else None,
            candidatos=[LinhaApuracaoResposta.de_linha(c) for c in resultado.candidatos],
        )


class ComparecimentoResposta(BaseModel):
    """Eleitores aptos (cadastrados antes da abertura), votantes e abstenção (RN-79)."""

    eleitores_aptos: int = Field(description="Eleitores cadastrados na eleição.", examples=[6])
    votantes: int = Field(description="Eleitores que votaram em pelo menos um cargo.")
    abstencao: int = Field(description="Aptos que não votaram em nenhum cargo.", examples=[2])


class ApuracaoResposta(BaseModel):
    """Apuração parcial (`tipo` PARCIAL) ou resultado final (`tipo` FINAL)."""

    model_config = ConfigDict(json_schema_extra={"example": _EXEMPLO})

    eleicao_id: int = Field(description="Eleição apurada.", examples=[1])
    tipo: Literal["PARCIAL", "FINAL"] = Field(description="PARCIAL (aberta) ou FINAL (encerrada).")
    status_eleicao: StatusEleicao = Field(description="Situação da eleição.")
    gerado_em: datetime = Field(description="Instante em que a apuração foi calculada.")
    comparecimento: ComparecimentoResposta = Field(description="Aptos, votantes e abstenção.")
    cargos: list[ResultadoCargoResposta] = Field(description="Um resultado por cargo.")

    @classmethod
    def de_apuracao(cls, apuracao: Apuracao) -> "ApuracaoResposta":
        comparecimento = apuracao.comparecimento
        return cls(
            eleicao_id=apuracao.eleicao_id,
            tipo=apuracao.tipo,
            status_eleicao=apuracao.status_eleicao,
            gerado_em=apuracao.gerado_em,
            comparecimento=ComparecimentoResposta(
                eleitores_aptos=comparecimento.eleitores_aptos,
                votantes=comparecimento.votantes,
                abstencao=comparecimento.abstencao,
            ),
            cargos=[ResultadoCargoResposta.de_resultado(c) for c in apuracao.cargos],
        )
