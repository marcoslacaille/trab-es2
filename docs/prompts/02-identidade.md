# Tarefa 02 — Identidade: usuários, login, JWT e perfis

Implemente o módulo `identidade`: a tabela de usuários, o login por CPF e senha, o token JWT de acesso, a proteção de rotas por perfil e o script que cria o Chefe da Seção.

**Branch:** `feat/identidade`

## Leia antes de começar

- `docs/PLANO.md`: seções 2, 5 (tabela de módulos e camadas), 6 (tabela `usuarios`), 7 (inteira), 8 (RN-01 a RN-08), 9.2, 10 (rotas `/auth/*` e contrato do login), 11 ("Botão Authorize"), 12 (TU-07 a TU-12 e TI-01 a TI-07) e 13 (Fase 2).
- Todo o código de `app/compartilhado/`.

## O que fazer

1. `app/identidade/modelos.py`: tabela `usuarios` com todas as colunas e restrições da seção 6 (nomes de restrição pela convenção). Registre o import em `app/registro_modelos.py`.
2. Migração `0001_identidade` (autogenerate + revisão manual). Teste `upgrade head` e `downgrade -1`.
3. `app/identidade/dominio.py`: `Perfil` (enum), `UsuarioAutenticado` (`dataclass` com `id`, `nome`, `cpf`, `perfil`), `validar_senha` (RN-05).
4. `app/identidade/senhas.py` e `app/identidade/tokens.py`: como na seção 7.
5. `app/identidade/repositorio.py`: consultas só na tabela `usuarios`.
6. `app/identidade/servico.py`: `autenticar`, `criar_credencial`, `atualizar_credencial`, `remover_credencial`, `obter_usuario`, `obter_usuarios`, `listar_usuarios` (seção 9.2). As funções para outros módulos **não fazem commit** (está na docstring).
7. `app/identidade/dependencias.py`: `esquema_oauth2`, `obter_usuario_atual`, `exige_perfil` (seção 7).
8. `app/identidade/esquemas.py` e `app/identidade/rotas.py`: `POST /auth/login` (formulário OAuth2; `username` = CPF) e `GET /auth/me`, com prefixo `/api/v1` via `main.py`, tag "Autenticação", `summary`, `description` e `responses=respostas_de_erro(...)`.
9. `app/scripts/__init__.py` e `app/scripts/criar_chefe.py`: lê `chefe_cpf`, `chefe_nome`, `chefe_senha` da configuração; valida; cria o usuário com perfil `CHEFE_SECAO` se o CPF não existir (idempotente); imprime uma mensagem sem a senha.
10. Fixtures e helpers de teste em `tests/auxiliares.py`: `gerar_cpf(semente)`, `criar_chefe()`, `login(cliente, cpf, senha)` e a fixture `cabecalho_chefe` (seção 12).

## Testes obrigatórios

- Unitários: **TU-07 a TU-12** (`tests/unitarios/test_identidade.py`).
- Integração: **TI-01 a TI-07** (`tests/integracao/test_auth_api.py`). Para o TI-07, apague o usuário direto pelo serviço com commit e use o token antigo.

## Não faça nesta tarefa

- Rotas de eleitores ou candidatos (o TI-07 apaga pelo serviço de identidade).
- Limite de tentativas de login (é extra opcional).

## Pronto quando

- Testes acima verdes, junto com os anteriores.
- `python -m app.scripts.criar_chefe` cria o Chefe com os dados do `.env` e, rodado de novo, não duplica.
- No Swagger local, o botão Authorize funciona com o CPF e a senha do Chefe, e `GET /api/v1/auth/me` responde com o perfil `CHEFE_SECAO`.

## Commits

1. `feat(identidade): cria tabela de usuários`
2. `feat(identidade): gera hash de senha com bcrypt`
3. `feat(identidade): emite e valida token de acesso`
4. `feat(identidade): adiciona login e consulta do usuário logado`
5. `feat(identidade): protege rotas por perfil`
6. `feat(scripts): cria chefe da seção inicial`
7. `test(identidade): cobre senhas, tokens e login` (inclui marcar a tarefa no PROGRESSO)

Depois do merge na `main`, crie a tag `v0.1.0` (o grupo faz isso).
