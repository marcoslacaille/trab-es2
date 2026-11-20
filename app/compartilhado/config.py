from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Configurações lidas de variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: str = "dev"
    database_url: str
    jwt_segredo: str = Field(min_length=32)
    jwt_expiracao_minutos: int = 60
    cedula_expiracao_minutos: int = 5
    bcrypt_custo: int = 12
    fuso_horario: str = "America/Sao_Paulo"
    # usados só pelo script criar_chefe
    chefe_cpf: str | None = None
    chefe_nome: str = "Chefe da Seção"
    chefe_senha: str | None = None


@lru_cache
def obter_configuracao() -> Configuracao:
    """Devolve a configuração da aplicação (lida uma única vez e guardada em cache)."""
    return Configuracao()
