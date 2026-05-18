from skills.whatsapp.utils.infrastructure import validate_infrastructure


def test_validate_infrastructure_shape():
    checks = validate_infrastructure()
    assert "machine_type" in checks
    assert "local_ollama" in checks
    assert "local_models" in checks
