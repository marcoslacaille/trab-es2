"""Service de usuários: login e credenciais. Não faz commit; quem chama controla a transação."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import ConflitoDeEstado, DadosInvalidos, NaoAutenticado
from app.core.paginacao import Pagina, Paginacao
from app.core.validadores import cpf_valido, normalizar_cpf
from app.dto.usuario_dto import ResultadoDoLogin, UsuarioAutenticado
from app.models.enums import Perfil
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository

NOME_MINIMO = 3
NOME_MAXIMO = 120
TAMANHO_MINIMO_SENHA = 8


def validar_senha(senha: str) -> None:
    """RN-05: de 8 caracteres até 72 bytes em UTF-8, e não pode ser só espaços.

    Levanta `DadosInvalidos` com o código `SENHA_INVALIDA` (422) se a senha não servir.
    """
    if senha.strip() == "":
        raise DadosInvalidos("A senha não pode conter apenas espaços.", codigo="SENHA_INVALIDA")
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise DadosInvalidos(
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.",
            codigo="SENHA_INVALIDA",
        )
    if len(senha.encode("utf-8")) > security.BYTES_MAXIMOS_SENHA:
        raise DadosInvalidos(
            f"A senha deve ter no máximo {security.BYTES_MAXIMOS_SENHA} bytes (UTF-8).",
            codigo="SENHA_INVALIDA",
        )


class UsuarioService:
    """Service de usuários: login, credenciais e consulta dos usuários.

    `criar_credencial`, `atualizar_credencial` e `remover_credencial` são pensados para outros
    services (eleitores, candidatos) e **não fazem commit**: quem chama controla a transação,
    para não ficar nada gravado pela metade.
    """

    def __init__(self, sessao: Session, repository: UsuarioRepository | None = None) -> None:
        self.sessao = sessao
        self.repository = repository or UsuarioRepository(sessao)

    @staticmethod
    def _para_usuario_autenticado(usuario: Usuario) -> UsuarioAutenticado:
        """Converte o modelo ORM na `dataclass` pública: o ORM não sai do service."""
        return UsuarioAutenticado(
            id=usuario.id, nome=usuario.nome, cpf=usuario.cpf, perfil=Perfil(usuario.perfil)
        )

    @staticmethod
    def _validar_nome(nome: str) -> str:
        """RN-08: de 3 a 120 caracteres, ignorando espaços nas pontas. Devolve o nome sem eles."""
        nome = nome.strip()
        if not NOME_MINIMO <= len(nome) <= NOME_MAXIMO:
            raise DadosInvalidos(
                f"O nome deve ter de {NOME_MINIMO} a {NOME_MAXIMO} caracteres.",
                codigo="DADOS_INVALIDOS",
            )
        return nome

    def autenticar(self, cpf: str, senha: str) -> ResultadoDoLogin:
        """RN-01: login por CPF e senha.

        Qualquer falha (CPF mal formatado, CPF inexistente ou senha errada) responde o mesmo 401
        `CREDENCIAIS_INVALIDAS`, com a mesma mensagem e tempo parecido: quando não há usuário, a
        senha é conferida contra um hash fictício. Não grava nada, então não faz commit.
        """
        cpf_normalizado = normalizar_cpf(cpf)
        usuario = self.repository.buscar_por_cpf(cpf_normalizado) if cpf_normalizado else None

        hash_conferido = usuario.senha_hash if usuario else security.hash_ficticio()
        senha_correta = security.senha_confere(senha, hash_conferido)
        if usuario is None or not senha_correta:
            raise NaoAutenticado("CPF ou senha inválidos.", codigo="CREDENCIAIS_INVALIDAS")

        token, expira_em = security.criar_token_acesso(usuario.id, Perfil(usuario.perfil))
        return ResultadoDoLogin(
            access_token=token,
            expira_em=expira_em,
            usuario=self._para_usuario_autenticado(usuario),
        )

    def criar_credencial(
        self, cpf: str, nome: str, senha: str, perfil: Perfil, agora: datetime
    ) -> int:
        """Cria o usuário e devolve o id. **Não faz commit**: quem chama controla a transação.

        RN-07: o CPF é normalizado (só dígitos), validado (`CPF_INVALIDO`, 422) e único
        (`CPF_JA_CADASTRADO`, 409). RN-05: a senha passa pela regra e só o hash é gravado.
        RN-08: o nome tem de 3 a 120 caracteres.
        """
        cpf_normalizado = normalizar_cpf(cpf)
        if not cpf_valido(cpf_normalizado):
            raise DadosInvalidos("CPF inválido.", codigo="CPF_INVALIDO")
        nome = self._validar_nome(nome)
        validar_senha(senha)
        if self.repository.buscar_por_cpf(cpf_normalizado) is not None:
            raise ConflitoDeEstado("Já existe um usuário com este CPF.", codigo="CPF_JA_CADASTRADO")

        usuario = Usuario(
            cpf=cpf_normalizado,
            nome=nome,
            senha_hash=security.gerar_hash(senha),
            perfil=perfil.value,
            criado_em=agora,
            atualizado_em=agora,
        )
        self.repository.inserir(usuario)
        return usuario.id

    def atualizar_credencial(
        self,
        usuario_id: int,
        agora: datetime,
        nome: str | None = None,
        senha: str | None = None,
    ) -> None:
        """Altera só o que veio (nome e/ou senha) e atualiza `atualizado_em`. **Não faz commit**.

        RN-05: a nova senha passa pela regra e só o hash é gravado. RN-08: o nome tem de 3 a 120
        caracteres. O CPF e o perfil nunca mudam (RN-03).
        """
        usuario = self._obter_modelo(usuario_id)
        if nome is not None:
            usuario.nome = self._validar_nome(nome)
        if senha is not None:
            validar_senha(senha)
            usuario.senha_hash = security.gerar_hash(senha)
        usuario.atualizado_em = agora
        self.sessao.flush()

    def remover_credencial(self, usuario_id: int) -> None:
        """Apaga o usuário. **Não faz commit**: quem chama controla a transação.

        Depois disso, qualquer token emitido para ele deixa de valer na hora (RN-02).
        """
        self.repository.remover(self._obter_modelo(usuario_id))

    def _obter_modelo(self, usuario_id: int) -> Usuario:
        """Quem chama já conhece o usuário, então a ausência é inconsistência (vira 500)."""
        usuario = self.repository.buscar_por_id(usuario_id)
        if usuario is None:
            raise LookupError(f"Usuário {usuario_id} não existe.")
        return usuario

    def obter_usuario(self, usuario_id: int) -> UsuarioAutenticado | None:
        """Devolve o usuário ou `None` se não existir (por exemplo, excluído depois do login)."""
        usuario = self.repository.buscar_por_id(usuario_id)
        return self._para_usuario_autenticado(usuario) if usuario else None

    def obter_usuarios(self, ids: list[int]) -> dict[int, UsuarioAutenticado]:
        """Devolve os usuários existentes, indexados pelo id (ids inexistentes ficam de fora)."""
        if not ids:
            return {}
        return {
            u.id: self._para_usuario_autenticado(u) for u in self.repository.buscar_por_ids(ids)
        }

    def listar_usuarios(
        self, perfil: Perfil, nome: str | None, paginacao: Paginacao
    ) -> Pagina[UsuarioAutenticado]:
        """Lista os usuários de um perfil, filtrando por parte do nome, ordenados por nome.

        Usada pelas listagens de eleitores e candidatos.
        """
        usuarios, total = self.repository.listar(perfil.value, nome, paginacao)
        return Pagina[UsuarioAutenticado](
            itens=[self._para_usuario_autenticado(u) for u in usuarios],
            pagina=paginacao.pagina,
            tamanho=paginacao.tamanho,
            total=total,
        )
