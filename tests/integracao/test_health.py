def test_health_responde_200_com_status_ok(cliente):
    """RN-06: o /health é público e confirma que a API e o banco estão no ar."""
    resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
