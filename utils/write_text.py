import validate


def write_text(filepath, text, *, mode="w", exist_ok=False):
    """
    Store a string as .txt file
    """
    assert validate.is_filepath(filepath, suffix=".txt", existing=None if exist_ok else False)
    assert validate.is_string(text, min_length=1)
    assert validate.is_string(mode)
    assert validate.is_bool(exist_ok)

    with open(filepath, mode) as f:
        f.write(text)
