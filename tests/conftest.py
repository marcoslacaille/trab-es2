import os

URL_TESTE = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://eleicao:eleicao@localhost:5433/eleicao_teste"
)
# Nos testes, a própria aplicação aponta para o banco de teste (nunca para o da demo)
os.environ["DATABASE_URL"] = URL_TESTE
os.environ["BCRYPT_CUSTO"] = "4"  # bcrypt rápido nos testes
os.environ.setdefault("JWT_SEGREDO", "segredo-de-teste-com-pelo-menos-32-caracteres")
