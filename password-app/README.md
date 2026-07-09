# Password App 🔐

A TypeScript CLI utility for **secure password hashing and verification**
using the **scrypt** key-derivation function (via Node.js `crypto`).

> ⚠️ **Why hashing, not encryption?** Passwords should never be stored in a
> recoverable form.  Hashing is a one-way function — even if the hash database
> is leaked, the original passwords cannot be reconstructed.  Encryption is
> reversible and is therefore **not** appropriate for password storage.

## Features

| Feature              | Details                                                    |
|----------------------|------------------------------------------------------------|
| Algorithm            | scrypt (N=16384, r=8, p=1 — OWASP 2023 recommendations)   |
| Salt                 | Random 16-byte salt generated per password                 |
| Key length           | 64 bytes (512 bits)                                        |
| Timing-safe verify   | Uses `crypto.timingSafeEqual` to prevent timing attacks    |
| Zero runtime deps    | Built entirely on Node.js `crypto` — no npm dependencies   |
| Encoded output       | `scrypt$<base64-salt>$<base64-hash>` — easy DB storage     |

## Quick Start

```bash
# Install dependencies & build
npm install
npm run build

# Hash a password
node dist/index.js hash "MyS3cur3P@ss!"
# → scrypt$c2FsdA==$hash==

# Verify a password
node dist/index.js verify "MyS3cur3P@ss!" "scrypt$c2FsdA==$hash=="
# → ✓ Password matches.
```

## Security Notes

- **scrypt** is deliberately slow and memory-hard, making GPU/ASIC attacks
  prohibitively expensive.
- A **unique random salt** is generated for every hash, preventing rainbow
  table and pre-computation attacks.
- Verification uses **constant-time comparison** (`crypto.timingSafeEqual`)
  to prevent timing side-channel attacks.
- For production systems, consider **Argon2id** (the current OWASP
  recommended algorithm) via the `argon2` npm package — scrypt is used here
  to keep the app dependency-free.

## License

MIT
