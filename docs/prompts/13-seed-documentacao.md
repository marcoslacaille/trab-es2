# Tarefa 13 — Dados de demonstração e documentação de entrega

Prepare tudo para a apresentação e para a entrega escrita: o script de dados de demonstração, o README completo (arquitetura, modularização e modelagem, como o enunciado pede), os documentos de apoio e a coleção do Postman.

**Branch:** `docs/entrega`

## Leia antes de começar

- `docs/PLANO.md`: seções 1, 5, 6, 7, 14, 15 e 16 (inteiras).
- O código de `app/` (para que a documentação descreva o que existe de verdade, não só o plano).

## O que fazer

1. **`app/scripts/seed_demo.py`** (seção 14): usa os **serviços** dos módulos (não SQL direto); chefe, 3 partidos, 6 eleitores, 10 candidatos e a eleição de hoje (00:00 às 23:59) com as 10 candidaturas, ainda AGENDADA; para com aviso se já houver dados; imprime a tabela de logins. Rode do banco limpo para conferir.
2. **`README.md` completo**, com os 12 itens da seção 15, na ordem. Diagramas em mermaid (módulos e ER). Tudo em português, escrito para o professor, e reproduzível numa máquina limpa (Windows e Linux/macOS).
3. **`docs/ARQUITETURA.md`**: seções 1, 3, 5 e 7 do PLANO, adaptadas ao código final, mais o diagrama de sequência do voto (seção 15).
4. **`docs/MODELAGEM.md`**: a seção 6 inteira, conferida contra as migrações reais (se algo mudou na implementação, documente o que existe).
5. **`docs/DEMO.md`**: o roteiro da seção 16 com as requisições exatas e as respostas esperadas.
6. **Coleção do Postman** em `docs/colecao-postman.json` (formato Collection v2.1): as requisições do roteiro, na ordem, com variáveis de ambiente (`base_url`, `token_chefe`, `token_eleitor`, `token_candidato`, `eleicao_id`, `token_cedula`) e os scripts de pós-resposta que guardam os tokens (seção 16). Inclua também `docs/ambiente-postman.json` com `base_url = http://localhost:8000/api/v1`.
7. Rode o roteiro inteiro do `DEMO.md` contra a API real (banco limpo → migrações → seed → uvicorn) e corrija qualquer divergência entre o documento e o comportamento.

## Não faça nesta tarefa

- Mudanças em regras de negócio. Divergências entre PLANO e código: anote no PROGRESSO e me pergunte qual vale.

## Pronto quando

- Do zero (`docker compose down -v`, `up -d`, `alembic upgrade head`, `seed_demo`, `uvicorn`), o roteiro do `DEMO.md` funciona inteiro no Postman importando a coleção.
- README com os 12 itens; `ARQUITETURA.md`, `MODELAGEM.md` e `DEMO.md` prontos.
- Todos os testes verdes.

## Commits

1. `feat(scripts): adiciona dados de demonstração`
2. `docs: descreve arquitetura e modularização`
3. `docs: descreve a modelagem do banco`
4. `docs: completa o README de entrega`
5. `docs: adiciona roteiro e coleção da demonstração` (inclui marcar a tarefa no PROGRESSO)

Depois do merge na `main`, crie a tag `v1.0.0`.
