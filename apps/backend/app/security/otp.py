import secrets

import bcrypt


def generate_code() -> str:
    # secrets, not random: the code guards a login step, so it must be
    # unpredictable even to an attacker who can observe many generations.
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_code(code: str, code_hash: str) -> bool:
    return bcrypt.checkpw(code.encode("utf-8"), code_hash.encode("utf-8"))
