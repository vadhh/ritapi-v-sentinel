# Version Pinning Security Annex

## Purpose

All Python dependencies in RITAPI V-Sentinel are pinned to exact versions (`==`) to ensure:
- **Reproducible builds** across all deployment targets
- **Supply-chain security** by preventing silent dependency updates
- **Audit compliance** with known, verified package versions

## Version Rationale

### Django Dashboard (`projects/ritapi_django/requirements.txt`)

| Package | Version | Rationale |
|---------|---------|-----------|
| Django | 4.2.28 | LTS release with security patches through April 2026 |
| cryptography | 43.0.3 | Latest stable; required for pyOpenSSL and TLS operations |
| psycopg2-binary | 2.9.9 | Stable PostgreSQL adapter; binary avoids C build deps |
| geoip2 | 5.2.0 | Latest MaxMind GeoIP2 API; backward-compatible with >=4.8.0 |
| pandas | 2.2.2 | Stable data processing; matches MiniFW version range |
| scikit-learn | 1.5.0 | ML inference compatibility with MiniFW models |

### MiniFW-AI Service (`projects/minifw_ai_service/requirements.txt`)

| Package | Version | Rationale |
|---------|---------|-----------|
| fastapi | 0.115.0 | Stable release with Pydantic v2 support |
| uvicorn | 0.32.0 | ASGI server matching FastAPI compatibility |
| pydantic | 2.10.0 | V2 data validation; required by FastAPI |
| sqlalchemy | 2.0.36 | 2.x ORM with async support |
| numpy | 1.26.4 | Last 1.x release; pinned <2.0.0 for legacy CPU compatibility (AVX/SSE4 SIGILL prevention) |
| pandas | 2.2.3 | Latest 2.x stable |
| scikit-learn | 1.5.2 | MLP inference engine compatibility |
| bcrypt | 3.2.2 | Pinned for passlib compatibility; 4.x breaks passlib bcrypt backend |
| yara-python | 4.5.1 | Includes bundled libyara C extension (fixes libyara.so crash) |
| python-jose | 3.3.0 | JWT handling with cryptography backend |

## Update Procedure

### Quarterly Review (Recommended)

1. Run `pip-audit` against both `requirements.txt` files:
   ```bash
   pip-audit -r projects/ritapi_django/requirements.txt
   pip-audit -r projects/minifw_ai_service/requirements.txt
   ```
2. Review GitHub Dependabot alerts (if enabled)
3. For each flagged package:
   - Check changelog for breaking changes
   - Test in isolated venv: `pip install -r requirements.txt`
   - Run full test suite: `python manage.py test` and `pytest testing/ -v`
   - Update version pin and commit

### Emergency Security Update

When a CVE is published for a pinned dependency:

1. **Assess impact**: Does the vulnerability affect V-Sentinel's usage of the package?
2. **Pin to patched version**: Update the exact version in `requirements.txt`
3. **Test locally**:
   ```bash
   python3 -m venv /tmp/test-venv && source /tmp/test-venv/bin/activate
   pip install -r requirements.txt
   # Run tests
   ```
4. **Deploy**: Run `install.sh` which generates `requirements.lock` for audit trail
5. **Verify**: Check `requirements.lock` in deployment directory matches expectations

## Lock File Generation

The installer (`install.sh`) generates `requirements.lock` files after each deployment:
- Django: `/opt/ritapi_v_sentinel/requirements.lock`
- MiniFW: `/opt/minifw_ai/requirements.lock`

These lock files capture the exact resolved versions (including transitive dependencies) for post-deployment audit.

## Constraints

- **numpy <2.0.0**: Required for legacy CPU support. NumPy 2.x uses AVX/AVX2/AVX-512 instructions that cause SIGILL on older hardware without these extensions.
- **bcrypt ==3.2.2**: passlib's bcrypt backend is incompatible with bcrypt 4.x due to API changes. Do not upgrade without verifying passlib compatibility.
- **Django 4.2.x LTS**: Pinned to LTS track. Do not upgrade to 5.x without full migration testing.
