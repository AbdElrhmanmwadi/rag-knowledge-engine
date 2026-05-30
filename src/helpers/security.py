import hashlib

import bcrypt


PASSWORD_HASH_PREFIX = "bcrypt_sha256$"


def _password_digest(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_password_digest(password), bcrypt.gensalt(rounds=12))
    return f"{PASSWORD_HASH_PREFIX}{hashed.decode('utf-8')}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(PASSWORD_HASH_PREFIX):
        stored_hash = hashed_password.removeprefix(PASSWORD_HASH_PREFIX).encode("utf-8")
        return bcrypt.checkpw(_password_digest(plain_password), stored_hash)

    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        return False

    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
