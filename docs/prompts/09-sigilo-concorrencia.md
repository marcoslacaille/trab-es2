# Tarefa 09 — Sigilo do voto e voto simultâneo

Prove com testes as duas garantias mais importantes da votação: **ninguém consegue descobrir em quem um eleitor votou**, e **duas confirmações simultâneas nunca geram dois votos**. Se algum teste revelar um problema, corrija o código (sem enfraquecer o teste).

**Branch:** `test/sigilo-concorrencia`

## Leia antes de começar

- `docs/PLANO.md`: seções 1 (D05 e D06), 6 ("Limitação conhecida do sigilo"), 7 ("Proteções aplicadas" e tabela de ameaças), 8 (RN-54 e RN-60), 9.6 (por que a confirmação não checa "já votou" antes) e 12 (TI-69 a TI-73).
- Todo o código de `app/votacao/`.

## O que fazer

1. `tests/integracao/test_sigilo.py`:
   - **TI-69:** com `sqlalchemy.inspect(engine)`, verifique que `votos` não tem coluna nem chave estrangeira para `eleitores` ou `usuarios` e não tem coluna de data/hora; e que `registros_votacao` não tem `candidatura_id` nem `tipo`.
   - **TI-70:** depois de um eleitor votar, chame `/participacao`, `/eleitores/eu`, `/auth/me` e guarde a resposta da confirmação; nenhuma delas pode conter o número nem o nome de urna escolhido.
   - **TI-71:** os IDs em `votos` são UUID versão 4.
   - **TI-72:** com `caplog` em nível DEBUG, registre e confirme um voto; o log não pode conter o token da cédula, o número nem o `candidatura_id`.
2. `tests/integracao/test_concorrencia.py`:
   - **TI-73:** emita uma cédula, abra **duas sessões** (`SessionLocal()`), e em duas threads sincronizadas por `threading.Barrier(2)` chame `votacao.servico.confirmar_voto` com a mesma cédula. Resultado: exatamente um sucesso, um `ConflitoDeEstado` com código `VOTO_JA_REGISTRADO`, e 1 linha em `votos`. Use o relógio de teste passando `agora` diretamente.
3. Se ainda não houver log de requisições, **não** crie agora (é da tarefa 11); o TI-72 deve passar com os logs que existirem.

## Não faça nesta tarefa

- Novas funcionalidades. Só testes e as correções que eles exigirem.

## Pronto quando

- TI-69 a TI-73 verdes, junto com todos os anteriores.
- Rode `.venv\Scripts\python.exe -m pytest tests/integracao/test_concorrencia.py` 5 vezes seguidas e confirme que nunca falha.

## Commits

1. `test(votacao): garante sigilo do voto no esquema, nas respostas e nos logs`
2. `test(votacao): garante voto único sob concorrência`
3. `fix(votacao): ...` (só se algum teste revelar problema; uma correção por commit)
4. Último commit inclui marcar a tarefa no PROGRESSO.

Depois do merge na `main`, crie a tag `v0.3.0`.
