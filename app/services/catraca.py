def catraca_cadastrada(catraca_id: str, config) -> bool:
    """Verifica se o identificador da catraca está na lista cadastrada."""
    if not isinstance(catraca_id, str) or not catraca_id.strip():
        return False

    cadastradas = config.get("CATRACAS_CADASTRADAS", set())
    return catraca_id.strip().upper() in cadastradas