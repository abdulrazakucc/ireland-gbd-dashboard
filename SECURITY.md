# Security and privacy policy

Global Health Evidence is an aggregate-data research application. It is not a
repository or processing environment for patient-, participant-, or
person-level data.

## Report a vulnerability

Do not open a public issue containing exploit details, credentials, private
hostnames, or research data. Use the repository's private security-advisory
workflow where available, or contact the principal investigator through the UCC profile
linked in the README. Include only the minimum information needed to reproduce
the problem and replace any real data with synthetic examples.

## Data boundary

- Only approved, aggregate IHME GBD exports belong in `data/incoming/`.
- The importer rejects common person, patient, participant, contact,
  credential, and direct-identifier columns.
- Incoming files, generated databases, prior databases, accounts, logs, process
  state, environment files, credentials, and private keys are excluded from Git
  and Docker build contexts.
- Public API provenance is de-identified. Original source filenames, paths,
  sizes, and hashes are not returned.

## Accounts and sessions

- Accounts live in `data/access/users.json`, written with owner-only
  permissions. Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a random
  per-account salt and 600,000 iterations, and must be at least 12 characters.
  Treat the file as a password database.
- A session is a signed, expiring, `HttpOnly`, `SameSite=Lax` cookie (also
  `Secure` in production). Every request re-checks it against the users file,
  so removing an account or changing its password ends its sessions at once.
- Failed sign-ins are rate limited per account and per client, sign-in posted
  from another site is refused, and an unknown email gets the same answer, in
  the same time, as a wrong password.
- The in-process rate limit suits a single server process. Running several
  processes for thousands of users requires moving accounts and rate limiting
  to a shared store first.

## GitHub Pages

A static site cannot check who is asking, so builds are allow-listed to one of
two shapes:

- **No accounts:** the landing page and two brand images only.
- **With accounts** (the `GBD_USERS_JSON` repository secret): also the
  application and its results, sealed with AES-256-GCM under a fresh random key
  on every build. That key is wrapped for each account with the account's
  PBKDF2-SHA256 password hash, which the reader's browser re-derives at sign-in.
  No readable estimate, email address, name, or password hash is published; the
  build and the Pages workflow both refuse to publish otherwise.

Its limits, which accounts on a server do not share:

- Anyone can download the sealed files and guess passwords offline, slowed only
  by the 600,000 PBKDF2 iterations. Use long, unique passwords for these accounts.
- Removing an account protects only the copies built afterwards; anyone who
  could open an earlier copy may have kept it.
- `GBD_USERS_JSON` contains password hashes: store it only as an Actions secret.

## Production requirements

Production startup fails unless sign-in is enforced: either
`GBD_AUTH_MODE=password` with a session secret of at least 32 unpredictable
characters, or `GBD_AUTH_MODE=proxy` behind an identity-aware reverse proxy with
a strong proxy secret. Prefer read-only mounted secret files
(`GBD_SESSION_SECRET_FILE`, `GBD_PROXY_SECRET_FILE`) over environment values.
For proxy mode, keep the application port private to the proxy, terminate TLS
there, strip inbound authentication headers, and inject the authenticated
identity and proxy secret only on the upstream request.

Before deployment:

1. Set `GBD_ENV=production`, `GBD_TRUSTED_HOSTS`, and either a session secret
   (password mode) or a proxy secret (proxy mode).
2. Leave `GBD_EXPOSE_DOCS` unset (off) and CORS empty unless there is a reviewed need.
3. Run `make check`; it includes tests, linting, and a vulnerability audit.
4. Confirm `make site` publishes only the allow-listed public files.
5. Serve over HTTPS, and confirm access review, audit, retention, and
   institutional incident-response requirements are met.

Security headers, no-store API caching, loopback-only local binding, non-root
containers, trusted-host validation, parameterised SQL, atomic imports, and
automated dependency updates provide defence in depth; none replaces the
authenticated deployment boundary.
