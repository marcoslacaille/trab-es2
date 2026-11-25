"""Testes do `CandidatoService`: nome de urna, nascimento e o que ele pede ao repository."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.dto.candidato_dto import AlteracoesCandidato
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.candidato import Candidato
from app.models.enums import Perfil
from app.repositories.candidato_repository import CandidatoRepository
from app.services.candidato_service import (
    CandidatoService,
    validar_nascimento_do_candidato,
    validar_nome_de_urna,
)
from app.services.usuario_service import UsuarioService

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
HOJE = AGORA.date()
FK_CANDIDATURA = "fk_candidaturas_candidato_id_candidatos"


def um_service() -> CandidatoService:
    """O service com repository, `UsuarioService` e sessão falsos: nada chega ao banco."""
    return CandidatoService(
        sessao=Mock(),
        repository=Mock(spec=CandidatoRepository),
        usuarios=Mock(spec=UsuarioService),
    )


def um_candidato() -> Candidato:
    return Candidato(
        id=3,
        usuario_id=9,
        nome_urna="Zeca",
        data_nascimento=date(1970, 1, 1),
        criado_em=AGORA,
    )


def um_erro_de_integridade(restricao: str | None) -> IntegrityError:
    """Um `IntegrityError` como o do PostgreSQL: o nome da restrição vem em `orig.diag`."""
    original = Exception("violação")
    original.diag = SimpleNamespace(constraint_name=restricao)
    return IntegrityError("DELETE ...", {}, original)


def test_nome_de_urna_fora_de_3_a_30_e_recusado():
    """RN-31: menos de 3 ou mais de 30 caracteres, sem contar as pontas, é recusado."""
    for nome_urna in ("Zé", "   ", "x" * 31):
        with pytest.raises(DadosInvalidos) as erro:
            validar_nome_de_urna(nome_urna)

        assert erro.value.codigo == "DADOS_INVALIDOS", repr(nome_urna)


def test_nome_de_urna_nos_limites_e_aceito():
    """RN-31: 3 e 30 caracteres passam, e os espaços das pontas não contam nem ficam."""
    assert validar_nome_de_urna("abc") == "abc"
    assert validar_nome_de_urna("x" * 30) == "x" * 30
    assert validar_nome_de_urna("  Carlos Lima ") == "Carlos Lima"


def test_nascimento_que_nao_esta_no_passado_e_recusado():
    """RN-31: nascer hoje ou no futuro é recusado com `DADOS_INVALIDOS`."""
    for nascimento in (HOJE, date(2027, 1, 1)):
        with pytest.raises(DadosInvalidos) as erro:
            validar_nascimento_do_candidato(nascimento, HOJE)

        assert erro.value.codigo == "DADOS_INVALIDOS", nascimento


def test_excluir_candidato_traduz_so_a_fk_da_candidatura():
    """RN-33: só a FK de `candidaturas` vira 409 `EXCLUSAO_BLOQUEADA`; outra violação sobe."""
    service = um_service()
    service.repository.buscar_candidato_por_id.return_value = um_candidato()

    service.repository.remover_candidato.side_effect = um_erro_de_integridade(FK_CANDIDATURA)
    with pytest.raises(ConflitoDeEstado) as bloqueada:
        service.excluir_candidato(3)

    service.repository.remover_candidato.side_effect = um_erro_de_integridade(None)
    with pytest.raises(IntegrityError):
        service.excluir_candidato(3)

    assert bloqueada.value.codigo == "EXCLUSAO_BLOQUEADA"
    assert service.sessao.rollback.call_count == 2
    service.usuarios.remover_credencial.assert_not_called()
    service.sessao.commit.assert_not_called()


def test_alterar_so_o_nome_de_urna_nao_mexe_na_credencial():
    """RN-31: sem nome nem senha no pedido, a credencial (nome e senha de login) fica como está."""
    service = um_service()
    candidato = um_candidato()
    service.repository.buscar_candidato_por_id.return_value = candidato
    service.usuarios.obter_usuarios.return_value = {
        9: UsuarioAutenticado(
            id=9, nome="Zeca da Silva", cpf="52998224725", perfil=Perfil.CANDIDATO
        )
    }

    resultado = service.atualizar_candidato(3, AlteracoesCandidato(nome_urna="  So Urna "), AGORA)

    assert candidato.nome_urna == "So Urna"
    assert (resultado.nome, resultado.nome_urna) == ("Zeca da Silva", "So Urna")
    service.usuarios.atualizar_credencial.assert_not_called()
    service.sessao.commit.assert_called_once_with()
