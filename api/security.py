"""수정용 비밀번호 발급·해시·검증."""
import hashlib
import hmac
import secrets

# 혼동하기 쉬운 문자(0 O 1 l I)를 뺀 알파벳
ALPHABET = "".join(c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789" if c not in "0O1lI")
PASSWORD_LENGTH = 12
ITERATIONS = 120_000


def generate_password() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(PASSWORD_LENGTH))


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def hash_password(password: str) -> str:
    """'pbkdf2_sha256$횟수$salt$hash' 형식 문자열을 반환한다."""
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, hash_hex = stored.split("$")
        expected = bytes.fromhex(hash_hex)
        actual = _derive(password, bytes.fromhex(salt_hex), int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)
