"""DTOs de votação: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import Cargo, ModoEscolha, TipoVoto


@dataclass(frozen=True)
class Escolha:
    """O resultado de `resolver_escolha`: o tipo do voto e, se nominal, o candidato escolhido.

    Só o voto NOMINAL tem candidatura. Os dados de exibição (número, nome de urna e sigla do
    partido) servem à prévia que o eleitor vê antes de confirmar; nos outros tipos ficam nulos.
    """

    tipo: TipoVoto
    candidatura_id: int | None = None
    numero: str | None = None
    nome_urna: str | None = None
    partido_sigla: str | None = None


@dataclass(frozen=True)
class ContagemVoto:
    """Quantos votos há de um tipo, para uma candidatura (ou nenhuma), em um cargo."""

    cargo: Cargo
    tipo: TipoVoto
    candidatura_id: int | None
    total: int


@dataclass(frozen=True)
class Comparecimento:
    """Quantos eleitores votaram em ao menos um cargo."""

    eleitores_que_votaram: int


@dataclass(frozen=True)
class PedidoRegistro:
    """O que o eleitor pede ao registrar o voto: o cargo e como escolhe (número ou BRANCO)."""

    cargo: Cargo
    modo: ModoEscolha
    numero: str | None = None


@dataclass(frozen=True)
class CandidatoDaCedula:
    """Como o candidato aparece para o eleitor na cédula e na prévia."""

    numero: str
    nome_urna: str
    partido_sigla: str


@dataclass(frozen=True)
class CargoDaCedula:
    """Um cargo disputado na cédula: dígitos do número, se o eleitor já votou e os candidatos."""

    cargo: Cargo
    digitos: int
    ja_votou: bool
    candidatos: list[CandidatoDaCedula]


@dataclass(frozen=True)
class CedulaDoEleitor:
    """A cédula da eleição: só os cargos disputados, na ordem da urna (RN-55)."""

    eleicao_id: int
    cargos: list[CargoDaCedula]


@dataclass(frozen=True)
class PreviaVoto:
    """O que o eleitor vê antes de confirmar. Nada foi gravado (RN-56)."""

    eleicao_id: int
    cargo: Cargo
    tipo: TipoVoto
    candidato: CandidatoDaCedula | None
    mensagem: str
    token_cedula: str
    expira_em: datetime


@dataclass(frozen=True)
class ComprovanteVoto:
    """A confirmação do voto. Não contém a escolha (RN-60)."""

    eleicao_id: int
    cargo: Cargo
    mensagem: str


@dataclass(frozen=True)
class CargoParticipacao:
    """Se o eleitor já votou em um cargo disputado. Nunca diz em quem (RN-61)."""

    cargo: Cargo
    ja_votou: bool


@dataclass(frozen=True)
class Participacao:
    """Em quais cargos da eleição o eleitor já votou (RN-61)."""

    eleicao_id: int
    cargos: list[CargoParticipacao]
