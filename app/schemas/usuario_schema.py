"""Schemas de usuário e login: o JSON de entrada e saída da API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Perfil


class UsuarioResposta(BaseModel):
    """Quem fez login (resumo devolvido junto com o token)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"id": 1, "nome": "Chefe da Seção", "perfil": "CHEFE_SECAO"}},
    )

    id: int = Field(description="Identificador do usuário.", examples=[1])
    nome: str = Field(description="Nome do usuário.", examples=["Chefe da Seção"])
    perfil: Perfil = Field(description="Perfil de acesso.", examples=["CHEFE_SECAO"])


class UsuarioLogadoResposta(BaseModel):
    """O usuário dono do token, como está no banco agora (`GET /auth/me`)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Chefe da Seção",
                "cpf": "29141777638",
                "perfil": "CHEFE_SECAO",
            }
        },
    )

    id: int = Field(description="Identificador do usuário.", examples=[1])
    nome: str = Field(description="Nome do usuário.", examples=["Chefe da Seção"])
    cpf: str = Field(description="CPF só com dígitos.", examples=["29141777638"])
    perfil: Perfil = Field(description="Perfil de acesso.", examples=["CHEFE_SECAO"])


class LoginResposta(BaseModel):
    """Resposta do login: o token a ser enviado em `Authorization: Bearer <token>`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expira_em": "2026-11-25T12:00:00Z",
                "usuario": {"id": 1, "nome": "Chefe da Seção", "perfil": "CHEFE_SECAO"},
            }
        }
    )

    access_token: str = Field(description="Token JWT de acesso.")
    token_type: Literal["bearer"] = Field(
        default="bearer", description="Tipo do token; sempre `bearer`."
    )
    expira_em: datetime = Field(description="Instante (UTC) em que o token deixa de valer.")
    usuario: UsuarioResposta = Field(description="Quem fez login.")
