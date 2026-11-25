"""Testes do `EleitorService`: idade, título, exclusão e cadastro, com dependências falsas."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.dto.eleitor_dto import NovoEleitorDados
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.eleitor import Eleitor
from app.models.enums import Perfil
from app.repositories.eleitor_repository import EleitorRepository
from app.services.eleitor_service import (
    EleitorService,
    validar_idade_eleitor,
    validar_titulo_eleitor,
)
from app.services.usuario_service import UsuarioService

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
HOJE = AGORA.date()
FK_VOTO = "fk_registros_votacao_eleitor_id_eleitores"


def um_service() -> EleitorService:
    """O service com repository, `UsuarioService` e sessão falsos: nada chega ao banco."""
    return EleitorService(
        sessao=Mock(),
        repository=Mock(spec=EleitorRepository),
        usuarios=Mock(spec=UsuarioService),
    )


def um_eleitor() -> Eleitor:
    return Eleitor(
        id=4,
        usuario_id=9,
        titulo_eleitor="100000000001",
        data_nascimento=date(2000, 1, 1),
        criado_em=AGORA,
    )


def um_erro_de_integridade(restricao: str | None) -> IntegrityError:
    """Um `IntegrityError` como o do PostgreSQL: o nome da restrição vem em `orig.diag`."""
    original = Exception("violação")
    original.diag = SimpleNamespace(constraint_name=restricao)
    return IntegrityError("DELETE ...", {}, original)


def codigo_da_recusa(validar, *argumentos) -> str:
    """Chama o validador, que precisa recusar, e devolve o código do erro."""
    with pytest.raises(DadosInvalidos) as erro:
        validar(*argumentos)
    return erro.value.codigo


@pytest.mark.parametrize(
    ("aceitos", "recusados"),
    [
        pytest.param([date(2010, 11, 25)], [], id="faz-16-hoje"),
        pytest.param(
            [], [date(2010, 11, 26), HOJE, date(2027, 1, 1)], id="faz-16-amanha-ou-futuro"
        ),
    ],
)
def test_idade_minima_de_16_anos(aceitos, recusados):
    """RN-22: quem faz 16 anos hoje passa; um dia a menos, ou nascer hoje ou no futuro, não."""
    for nascimento in aceitos:
        validar_idade_eleitor(nascimento, HOJE)
    for nascimento in recusados:
        assert codigo_da_recusa(validar_idade_eleitor, nascimento, HOJE) == "IDADE_MINIMA"


@pytest.mark.parametrize(
    ("aceitos", "recusados"),
    [
        pytest.param(["100000000001"], ["10000000000", "1000000000011", ""], id="tamanho-errado"),
        pytest.param(
            [],
            ["10000000000a", "١٠٠٠٠٠٠٠٠٠٠١"],  # o segundo: 12 dígitos arábico-índicos
            id="letras-ou-outro-alfabeto",
        ),
    ],
)
def test_titulo_de_eleitor_precisa_de_12_digitos(aceitos, recusados):
    """RN-21: o título tem exatamente 12 dígitos de 0 a 9."""
    for titulo in aceitos:
        validar_titulo_eleitor(titulo)
    for titulo in recusados:
        assert codigo_da_recusa(validar_titulo_eleitor, titulo) == "DADOS_INVALIDOS", titulo


def test_excluir_eleitor_traduz_so_a_fk_do_voto():
    """RN-24: só a FK de `registros_votacao` vira 409 `EXCLUSAO_BLOQUEADA`; outra violação sobe."""
    service = um_service()
    service.repository.buscar_por_id.return_value = um_eleitor()

    service.repository.remover.side_effect = um_erro_de_integridade(FK_VOTO)
    with pytest.raises(ConflitoDeEstado) as bloqueada:
        service.excluir_eleitor(4)

    service.repository.remover.side_effect = um_erro_de_integridade(None)
    with pytest.raises(IntegrityError):
        service.excluir_eleitor(4)

    assert bloqueada.value.codigo == "EXCLUSAO_BLOQUEADA"
    assert service.sessao.rollback.call_count == 2
    service.usuarios.remover_credencial.assert_not_called()
    service.sessao.commit.assert_not_called()


def test_cadastrar_eleitor_cria_a_credencial_o_eleitor_e_faz_commit():
    """RN-20 e RN-21: cria a credencial, insere o eleitor e faz um único commit, nessa ordem."""
    service = um_service()
    passos = []
    service.repository.buscar_por_titulo.return_value = None
    service.usuarios.criar_credencial.side_effect = lambda *argumentos: (
        passos.append("credencial") or 9
    )
    service.repository.inserir.side_effect = lambda eleitor: passos.append("eleitor")
    service.sessao.commit.side_effect = lambda: passos.append("commit")
    service.usuarios.obter_usuarios.return_value = {
        9: UsuarioAutenticado(id=9, nome="Ana Souza", cpf="52998224725", perfil=Perfil.ELEITOR)
    }
    dados = NovoEleitorDados(
        nome="Ana Souza",
        cpf="529.982.247-25",
        titulo_eleitor="100000000001",
        data_nascimento=date(2000, 1, 1),
        senha="Senha@2026",
    )

    cadastrado = service.cadastrar_eleitor(dados, AGORA)

    assert passos == ["credencial", "eleitor", "commit"]
    service.usuarios.criar_credencial.assert_called_once_with(
        dados.cpf, dados.nome, dados.senha, Perfil.ELEITOR, AGORA
    )
    inserido = service.repository.inserir.call_args.args[0]
    assert (inserido.usuario_id, inserido.titulo_eleitor, inserido.criado_em) == (
        9,
        "100000000001",
        AGORA,
    )
    assert (cadastrado.nome, cadastrado.titulo_eleitor) == ("Ana Souza", "100000000001")
