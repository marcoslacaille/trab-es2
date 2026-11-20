from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.candidatos.rotas import roteador as rotas_candidatos
from app.compartilhado.banco import obter_sessao
from app.compartilhado.erros import registrar_tratadores
from app.compartilhado.openapi import DESCRICAO_API, TAGS
from app.eleicoes.rotas import roteador as rotas_eleicoes
from app.eleicoes.rotas import roteador_candidaturas as rotas_candidaturas
from app.eleitores.rotas import roteador as rotas_eleitores
from app.identidade.rotas import roteador as rotas_identidade
from app.votacao.rotas import roteador as rotas_votacao

app = FastAPI(
    title="API de Simulação de Eleição Eletrônica",
    version="1.0.0",
    description=DESCRICAO_API,
    openapi_tags=TAGS,
    # operationId legível no Swagger (ex.: "abrir"); os nomes das funções de rota são únicos.
    generate_unique_id_function=lambda rota: rota.name,
)
registrar_tratadores(app)

PREFIXO = "/api/v1"
app.include_router(rotas_identidade, prefix=PREFIXO)
app.include_router(rotas_eleicoes, prefix=PREFIXO)
app.include_router(rotas_candidaturas, prefix=PREFIXO)
app.include_router(rotas_eleitores, prefix=PREFIXO)
app.include_router(rotas_candidatos, prefix=PREFIXO)
app.include_router(rotas_votacao, prefix=PREFIXO)


@app.get("/health", tags=["Sistema"], summary="Verifica se a API e o banco estão no ar")
def health(sessao: Annotated[Session, Depends(obter_sessao)]) -> dict:
    """Executa `SELECT 1` no banco. Responde 200 com `{"status": "ok"}` se tudo estiver no ar."""
    sessao.execute(text("SELECT 1"))
    return {"status": "ok"}
