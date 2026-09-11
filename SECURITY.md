# Security and privacy policy

Global Health Evidence is an aggregate-data research application. It is not a
repository or processing environment for patient-, participant-, or
person-level data.

## Report a vulnerability

Do not open a public issue containing exploit details, credentials, private
hostnames, or research data. Use the repository's private security-advisory
workflow where available, or contact the research lead through the UCC profile
linked in the README. Include only the minimum information needed to reproduce
the problem and replace any real data with synthetic examples.

## Data boundary

- Only approved, aggregate IHME GBD exports belong in `data/incoming/`.
- The importer rejects common person, patient, participant, contact,
  credential, and direct-identifier columns.
- Incoming files, generated databases, prior databases, logs, process state,
  environment files, credentials, and private keys are excluded from Git and
  Docker build contexts.
- Public GitHub Pages builds are allow-listed to the landing page and two brand
  images. They contain no estimates, exports, dashboard code, or API settings.
- Public API provenance is de-identified. Original source filenames, paths,
  sizes, and hashes are not returned.

## Production requirements

Production startup fails unless proxy authentication and a strong proxy secret
are configured. Keep the application port private to an identity-aware reverse
proxy, terminate TLS there, strip inbound authentication headers, and inject
the authenticated identity and proxy secret only on the upstream request.
Prefer a read-only mounted secret file (`GBD_PROXY_SECRET_FILE`) over an
environment value.

Before deployment:

1. Set `GBD_ENV=production`, `GBD_AUTH_MODE=proxy`, `GBD_TRUSTED_HOSTS`, and a
   proxy secret of at least 32 unpredictable characters.
2. Leave `GBD_EXPOSE_DOCS` unset (off) and CORS empty unless there is a reviewed need.
3. Run `make check`; it includes tests, linting, and a vulnerability audit.
4. Confirm `make site` publishes only the allow-listed public files.
5. Confirm the reverse proxy applies access review, rate limits, audit policy,
   retention policy, and institutional incident-response requirements.

Security headers, no-store API caching, loopback-only local binding, non-root
containers, trusted-host validation, parameterised SQL, atomic imports, and
automated dependency updates provide defence in depth; none replaces the
authenticated deployment boundary.
