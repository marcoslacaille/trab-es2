"""Textos e utilitários da documentação Swagger/OpenAPI (seção 11 do PLANO)."""

from app.compartilhado.erros import ErroResposta

DESCRICAO_API = """
API de simulação de eleição eletrônica (trabalho de Engenharia de Software II).

**Como autenticar:** clique em *Authorize*, informe o CPF em `username` e a senha em `password`.

**Fluxo do voto:** consulte a cédula → registre o voto (recebe `token_cedula`) →
confirme com o token.

**Erros:** todas as rotas respondem `{"erro": {"codigo", "mensagem", "detalhes"}}`.
"""

TAGS = [
    {"name": "Sistema", "description": "Saúde da aplicação."},
    {"name": "Autenticação", "description": "Login e dados do usuário logado."},
    {
        "name": "Eleições",
        "description": "Cadastro, abertura, encerramento e situação (Chefe da Seção).",
    },
    {
        "name": "Candidaturas",
        "description": "Associação de candidato a eleição, cargo, partido e número.",
    },
    {"name": "Eleitores", "description": "Cadastro de eleitores (Chefe da Seção)."},
    {"name": "Candidatos", "description": "Cadastro de candidatos (Chefe da Seção)."},
    {"name": "Partidos", "description": "Cadastro e consulta de partidos."},
    {"name": "Votação", "description": "Cédula, registro e confirmação do voto (Eleitor)."},
    {"name": "Apuração", "description": "Acompanhamento parcial e resultado final."},
]

_DESCRICOES = {
    401: "Não autenticado ou token inválido",
    403: "Perfil sem permissão para esta operação",
    404: "Recurso não encontrado",
    409: "Conflito com o estado atual (regra de negócio)",
    422: "Dados inválidos",
}


def respostas_de_erro(*codigos_http: int) -> dict:
    """Monta o 'responses' de uma rota com o formato padrão de erro.

    Aceita os status 401, 403, 404, 409 e 422. Uso: `responses=respostas_de_erro(401, 403, 404)`.
    """
    return {
        codigo: {"model": ErroResposta, "description": _DESCRICOES[codigo]}
        for codigo in codigos_http
    }
