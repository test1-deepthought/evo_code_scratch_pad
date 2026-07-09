import * as crypto from 'crypto';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Length of the randomly generated salt in bytes. */
const SALT_LENGTH = 16;

/** Length of the derived key in bytes. */
const KEY_LENGTH = 64;

/**
 * Scrypt cost parameters.
 *
 *   N  – CPU / memory cost (must be a power of 2).
 *   r  – Block-size parameter.
 *   p  – Parallelization parameter.
 *
 * These values follow the OWASP 2023 recommendations for interactive logins
 * and are intentionally high enough to resist GPU / ASIC attacks while still
 * being acceptable (< 1 s) on modern hardware.
 */
const SCRYPT_N = 16384;   // 2^14
const SCRYPT_R = 8;
const SCRYPT_P = 1;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HashResult {
  /**
   * The complete encoded hash string (format: `algorithm$salt$hash`)
   * ready to be stored in a database column.
   */
  encoded: string;

  /** Algorithm identifier (always `"scrypt"` for this implementation). */
  algorithm: string;

  /** Random base64 salt that was generated and used. */
  salt: string;

  /** The raw derived-key hash encoded as base64. */
  hash: string;

  /** Scrypt parameters that were used. */
  params: { N: number; r: number; p: number };
}

// ---------------------------------------------------------------------------
// Core API
// ---------------------------------------------------------------------------

/**
 * Hash a plain-text password using scrypt.
 *
 * @param password - The plain-text password to hash.
 * @returns A {@link HashResult} containing the encoded string and metadata.
 */
export function hashPassword(password: string): HashResult {
  if (!password || typeof password !== 'string') {
    throw new Error('Password must be a non-empty string.');
  }

  const salt = crypto.randomBytes(SALT_LENGTH).toString('base64');
  const derivedKey = crypto.scryptSync(password, salt, KEY_LENGTH, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });

  const hash = derivedKey.toString('base64');
  const encoded = `scrypt$${salt}$${hash}`;

  return {
    encoded,
    algorithm: 'scrypt',
    salt,
    hash,
    params: { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P },
  };
}

/**
 * Verify a plain-text password against a previously encoded hash string.
 *
 * @param password   - The plain-text password to check.
 * @param encoded    - The encoded hash string previously produced by
 *                     {@link hashPassword}.
 * @returns `true` if the password matches the hash, `false` otherwise.
 */
export function verifyPassword(password: string, encoded: string): boolean {
  if (!password || typeof password !== 'string') {
    throw new Error('Password must be a non-empty string.');
  }
  if (!encoded || typeof encoded !== 'string') {
    throw new Error('Encoded hash must be a non-empty string.');
  }

  // Parse the stored encoded string: algorithm$salt$hash
  const parts = encoded.split('$');
  if (parts.length !== 3) {
    throw new Error(
      'Invalid encoded hash format. Expected "algorithm$salt$hash".'
    );
  }

  const [algorithm, salt, expectedHash] = parts;

  if (algorithm !== 'scrypt') {
    throw new Error(`Unsupported algorithm "${algorithm}".`);
  }

  if (!salt || !expectedHash) {
    throw new Error('Encoded hash contains empty salt or hash components.');
  }

  // Re-derive the key using the stored salt
  const derivedKey = crypto.scryptSync(password, salt, KEY_LENGTH, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });

  const computedHash = derivedKey.toString('base64');

  // Constant-time comparison to prevent timing attacks
  return crypto.timingSafeEqual(
    Buffer.from(computedHash, 'utf-8'),
    Buffer.from(expectedHash, 'utf-8')
  );
}
