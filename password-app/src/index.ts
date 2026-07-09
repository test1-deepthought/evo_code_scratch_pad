#!/usr/bin/env node

import { hashPassword, verifyPassword } from './password';

// ---------------------------------------------------------------------------
// Help text
// ---------------------------------------------------------------------------

const HELP = `
Password App  —  Secure password hashing & verification using scrypt

USAGE
  password-app hash <password>
      Hash a password and print the encoded hash string.

  password-app verify <password> <encoded-hash>
      Verify a password against an encoded hash.  Exits with code 0 if the
      password matches, 1 otherwise.

  password-app help
      Show this help message.

EXAMPLES
  password-app hash "MyS3cur3P@ss!"
  password-app verify "MyS3cur3P@ss!" "scrypt$<salt>$<hash>"
`;

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  const [, , command, ...args] = process.argv;

  switch (command) {
    case 'hash': {
      if (args.length < 1) {
        console.error('Error: Missing password argument.');
        console.error('Usage: password-app hash <password>');
        process.exit(1);
      }

      const password = args.join(' ');
      try {
        const result = hashPassword(password);
        console.log(result.encoded);
      } catch (err) {
        console.error('Error:', (err as Error).message);
        process.exit(1);
      }
      break;
    }

    case 'verify': {
      if (args.length < 2) {
        console.error('Error: Missing arguments.');
        console.error('Usage: password-app verify <password> <encoded-hash>');
        process.exit(1);
      }

      // The encoded hash is always the last argument; everything before it is
      // the password (supports passwords containing spaces).
      const encoded = args[args.length - 1];
      const password = args.slice(0, -1).join(' ');

      try {
        const valid = verifyPassword(password, encoded);
        if (valid) {
          console.log('✓ Password matches.');
          process.exit(0);
        } else {
          console.log('✗ Password does NOT match.');
          process.exit(1);
        }
      } catch (err) {
        console.error('Error:', (err as Error).message);
        process.exit(1);
      }
      break;
    }

    case 'help':
    case '--help':
    case '-h':
    case undefined: {
      console.log(HELP);
      break;
    }

    default: {
      console.error(`Unknown command: "${command}"`);
      console.error('Run "password-app help" for usage information.');
      process.exit(1);
    }
  }
}

main();
