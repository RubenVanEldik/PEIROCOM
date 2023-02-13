import validate


def calculate_crf(wacc, economic_lifetime):
    """
    Calculate the Capital Recovery Factor for a WACC and lifetime
    """
    assert validate.is_number(wacc)
    assert validate.is_number(economic_lifetime)

    return wacc / (1 - (1 + wacc) ** (-economic_lifetime))
