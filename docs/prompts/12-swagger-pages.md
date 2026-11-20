# Tarefa 12 — Documentação Swagger e link público no GitHub Pages

Deixe a documentação da API no nível de entrega: toda rota com resumo, descrição, exemplos realistas e respostas de erro, e a especificação publicada num link público (entregável "link da documentação da API").

**Branch:** `docs/swagger`

## Leia antes de começar

- `docs/PLANO.md`: seções 10 (contratos), 11 (inteira), 12 (TA-03) e 14 (valores realistas para os exemplos).
- Todos os `rotas.py` e `esquemas.py`.

## O que fazer

1. Revise **cada rota**: `summary` curto em português, `description` com as regras (citando RN-xx), `response_model`, `status_code`, `tags` e `responses=respostas_de_erro(...)` com todos os erros possíveis daquela rota.
2. Revise **cada esquema**: `Field(description=..., examples=[...])` com os valores da seção 14 (CPFs válidos, nomes, números). Nada de `"string"` ou `0` nos exemplos.
3. Confira `DESCRICAO_API` e `TAGS` (seção 11) e que o botão Authorize funciona.
4. `app/scripts/exportar_openapi.py`: grava `json.dumps(app.openapi(), ensure_ascii=False, indent=2)` em `docs/openapi.json`.
5. `docs/index.html`: exatamente como na seção 11 (Swagger UI pelo CDN, lendo `openapi.json`).
6. **TA-03** em `tests/arquitetura/test_openapi.py`: `app.openapi()` igual ao conteúdo de `docs/openapi.json`; se falhar, a mensagem diz "Rode python -m app.scripts.exportar_openapi".
7. No README, adicione a seção "Documentação da API" com o link local (`/docs`) e um espaço para o link do GitHub Pages.
8. Me passe o passo a passo para ativar o GitHub Pages (Settings → Pages → Deploy from a branch → `main` → `/docs`), que eu faço depois do merge.

## Não faça nesta tarefa

- Mudança de comportamento de rotas ou regras. Se encontrar um erro de comportamento, anote no PROGRESSO e me avise.

## Pronto quando

- Abrindo `http://localhost:8000/docs`, todas as rotas têm resumo, descrição, exemplos e erros documentados.
- `docs/openapi.json` gerado e TA-03 verde.
- Abrindo `docs/index.html` localmente (por um servidor simples, ex.: `.venv\Scripts\python.exe -m http.server -d docs`), o Swagger UI carrega a especificação.

## Commits

1. `docs: documenta rotas com exemplos e erros`
2. `docs: exporta a especificação OpenAPI`
3. `docs: adiciona Swagger UI estático para o GitHub Pages`
4. `test: garante que a especificação publicada está atualizada` (inclui marcar a tarefa no PROGRESSO)
