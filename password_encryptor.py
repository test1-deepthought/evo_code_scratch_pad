"""
password_encryptor.py — Secure password hashing with PBKDF2-HMAC-SHA256.

Uses only the Python standard library (hashlib, os, base64).
Passwords are hashed (one-way), never encrypted (reversible), and never stored
in plaintext.  Each hash includes a unique 128-bit random salt.

Storage format: pbkdf2$<algo>$<iterations>$<base64-salt>$<base64-hash>

Usage:
    python password_encryptor.py hash <password>
    python password_encryptor.py verify <password> <stored_hash>
"""

import hashlib
import os
import base64

# ─── Configuration ─────────────────────────────────────
ALGORITHM     = 'sha256'
ITERATIONS    = 600_000      # OWASP 2023 minimum for SHA256
SALT_LENGTH   = 16           # 128-bit salt
HASH_LENGTH   = 32           # 256-bit derived key


def generate_salt(length: int = SALT_LENGTH) -> bytes:
    """Return *length* cryptographically random bytes."""
    return os.urandom(length)


def hash_password(password: str, salt: bytes | None = None) -> str:
    """
    Hash *password* with a random 16-byte salt using PBKDF2-HMAC-SHA256.

    Returns a self-describing string of the form:
        pbkdf2$sha256$600000$<base64-salt>$<base64-hash>

    The plaintext password is never stored or returned.
    """
    if salt is None:
        salt = generate_salt()
    pw_bytes = password.encode('utf-8')
    dk = hashlib.pbkdf2_hmac(ALGORITHM, pw_bytes, salt, ITERATIONS)
    return (
        f"pbkdf2${ALGORITHM}${ITERATIONS}"
        f"${base64.b64encode(salt).decode('ascii')}"
        f"${base64.b64encode(dk).decode('ascii')}"
    )


def _constant_time_compare(a: bytes, b: bytes) -> bool:
    """
    Return True iff *a* and *b* are equal.

    Comparison uses bitwise XOR over every byte pair so that it runs in
    constant time independent of how many bytes match.  This prevents
    timing side-channel attacks.
    """
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


def verify_password(password: str, stored: str) -> bool:
    """
    Verify *password* against a hash string previously returned by
    :func:`hash_password`.

    Returns ``True`` if *password* matches, ``False`` otherwise.
    """
    parts = stored.split('$')
    if len(parts) != 5 or parts[0] != 'pbkdf2':
        raise ValueError(
            f"Expected format 'pbkdf2$algo$iters$salt$hash', got {stored!r}"
        )

    _, algo, iters_str, salt_b64, expected_b64 = parts
    iters    = int(iters_str)
    salt     = base64.b64decode(salt_b64)
    expected = base64.b64decode(expected_b64)

    actual = hashlib.pbkdf2_hmac(algo, password.encode('utf-8'), salt, iters)
    return _constant_time_compare(actual, expected)


def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  password_encryptor.py hash <password>")
        print("  password_encryptor.py verify <password> <stored_hash>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == 'hash':
        print(hash_password(sys.argv[2]))
    elif cmd == 'verify':
        ok = verify_password(sys.argv[2], sys.argv[3])
        print("\u2713 Match" if ok else "\u2717 No match")
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


# ─── Self-test ─────────────────────────────────────────
if __name__ == '__main__':
    test = "MySecureP@ssw0rd!"
    h1 = hash_password(test)
    assert verify_password(test, h1),        "correct password must verify"
    assert not verify_password(test + "x", h1), "wrong password must fail"
    assert not verify_password("", h1),         "empty password must fail"

    h2 = hash_password(test)
    assert h1 != h2, "same password must produce different hashes (different salt)"
    assert verify_password(test, h2), "second hash must also verify"

    print("All self-tests passed!")
