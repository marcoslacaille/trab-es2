"""Service de partidos: casos de uso e transação, com a regra de sigla, nome e número."""

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.dto.partido_dto import NovoPartidoDados, PartidoResumo
from app.models.partido import Partido
from app.repositories.partido_repository import PartidoRepository

FORMATO_SIGLA = re.compile(r"^[A-Z0-9]{2,10}$")
NOME_MAXIMO_DO_PARTIDO = 100
NUMERO_MINIMO_DO_PARTIDO = 10
NUMERO_MAXIMO_DO_PARTIDO = 99


def validar_partido(dados: NovoPartidoDados) -> NovoPartidoDados:
    """RN-32: confere os dados do partido e devolve-os normalizados.

    A sigla vira maiúscula e deve ter de 2 a 10 letras ou dígitos; o nome, sem espaços nas
    pontas, não pode ser vazio nem passar de 100 caracteres; o número fica entre 10 e 99.
    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se algo estiver errado.
    """
    sigla = dados.sigla.strip().upper()
    nome = dados.nome.strip()
    if not FORMATO_SIGLA.fullmatch(sigla):
        raise DadosInvalidos(
            "A sigla deve ter de 2 a 10 letras ou dígitos.", codigo="DADOS_INVALIDOS"
        )
    if not nome or len(nome) > NOME_MAXIMO_DO_PARTIDO:
        raise DadosInvalidos(
            f"O nome do partido deve ter de 1 a {NOME_MAXIMO_DO_PARTIDO} caracteres.",
            codigo="DADOS_INVALIDOS",
        )
    if not NUMERO_MINIMO_DO_PARTIDO <= dados.numero <= NUMERO_MAXIMO_DO_PARTIDO:
        raise DadosInvalidos(
            f"O número do partido deve ficar entre {NUMERO_MINIMO_DO_PARTIDO} e "
            f"{NUMERO_MAXIMO_DO_PARTIDO}.",
            codigo="DADOS_INVALIDOS",
        )
    return NovoPartidoDados(sigla=sigla, nome=nome, numero=dados.numero)


class PartidoService:
    """Service de partidos: casos de uso e transação."""

    def __init__(self, sessao: Session, repository: PartidoRepository | None = None) -> None:
        self.sessao = sessao
        self.repository = repository or PartidoRepository(sessao)

    @staticmethod
    def _resumir_partido(partido: Partido) -> PartidoResumo:
        """Converte o modelo no resumo do domínio. O ORM não sai do service."""
        return PartidoResumo(
            id=partido.id, sigla=partido.sigla, nome=partido.nome, numero=partido.numero
        )

    def criar_partido(self, dados: NovoPartidoDados, agora: datetime) -> PartidoResumo:
        """Cadastra um partido e faz commit (RN-32).

        A sigla é gravada em maiúsculas. Sigla, nome ou número já existentes dão 409
        `PARTIDO_DUPLICADO`; dados fora do formato dão 422 `DADOS_INVALIDOS`.
        """
        dados = validar_partido(dados)
        if self.repository.existe_partido_com(dados.sigla, dados.nome, dados.numero):
            raise ConflitoDeEstado(
                "Já existe um partido com esta sigla, nome ou número.",
                codigo="PARTIDO_DUPLICADO",
            )
        partido = Partido(sigla=dados.sigla, nome=dados.nome, numero=dados.numero, criado_em=agora)
        self.repository.inserir_partido(partido)
        self.sessao.commit()
        return self._resumir_partido(partido)

    def listar_partidos(self) -> list[PartidoResumo]:
        """Todos os partidos, ordenados por número (RN-30: qualquer usuário logado pode listar)."""
        partidos = self.repository.listar_partidos_por_numero()
        return [self._resumir_partido(partido) for partido in partidos]

    def obter_partido(self, partido_id: int) -> PartidoResumo | None:
        """Devolve o partido ou `None` se não existir. Usada por `eleicoes` (RN-46)."""
        partido = self.repository.buscar_partido_por_id(partido_id)
        return self._resumir_partido(partido) if partido else None
