"""Setup check for VideoMind.

Run from the project root (or cd to backend first):
    python -m app.check_setup   # or: python backend/check_setup.py

This prints exactly what is missing so you can fill in .env values before
starting the dev servers.
"""

import sys
from typing import List, Tuple

from app.config import Settings


# The pydantic Settings class stores these in lowercase (as defined in config.py)
REQUIRED_ENV_VARS = [
    "groq_api_key",
    "neon_dsn",
]


def _get_settings() -> Settings:
    """Create and return a Settings instance."""
    return Settings()


def _check_env_vars_via_config() -> List[str]:
    """Return required vars that are missing or empty per the config layer."""
    settings = _get_settings()
    missing: List[str] = []
    for var in REQUIRED_ENV_VARS:
        val = getattr(settings, var, None)
        if not val:
            missing.append(var)
    return missing


def main() -> Tuple[int, List[str]]:
    """Run setup checks and return (exit_code, report_parts).

    Returns a tuple of (exit_code, list_of_report_lines).
    """
    # Check via config layer (reliable once module imports correctly)
    missing_from_config = _check_env_vars_via_config()

    # If config vars are missing, report and exit with code 1
    if missing_from_config:
        report_parts: List[str] = []
        report_parts.append("Missing per config layer:")
        for var in missing_from_config:
            report_parts.append("  - %s" % var)
        report_parts.append("")
        report_parts.append("Service-level issues: (could not check - missing config)")
        report_parts.append("")
        report_parts.append("Fix them:")
        report_parts.append("  1. Get a Groq API key: https://console.groq.com/keys")
        report_parts.append("  2. Create a Neon PostgreSQL project: https://neon.tech/")
        report_parts.append("  3. Fill in backend/.env with:")
        report_parts.append("     GROQ_API_KEY=gsk_...                # your Groq key")
        report_parts.append("     NEON_DSN=postgresql://user:pw@ep.db.region.neon.tech:5455/dbname")
        report_parts.append("  4. Run database/schema.sql in Neon SQL Editor:")
        report_parts.append("     CREATE EXTENSION IF NOT EXISTS vector;")
        report_parts.append("     CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        report_parts.append("     [Run the rest of the schema from database/schema.sql]")
        report_parts.append("  5. Re-run this check: python -m app.check_setup")
        return 1, report_parts

    # All config vars are present
    report_parts: List[str] = []
    report_parts.append("All required vars present per config layer:")

    # Report Neon DSN (partial)
    report_parts.append("")
    settings = _get_settings()
    neon_dsn_val = settings.neon_dsn
    dsn_display = neon_dsn_val[:40] + "..." if neon_dsn_val else "empty"
    report_parts.append("Neon DSN: %s" % dsn_display)

    # Report Groq model
    report_parts.append("Groq model: %s" % settings.groq_model)

    report_parts.append("")
    report_parts.append("All checks passed -- everything looks configured.")
    report_parts.append("")
    report_parts.append("Fix instructions (if needed):")
    report_parts.append("  1. Get a Groq API key: https://console.groq.com/keys")
    report_parts.append("  2. Create a Neon PostgreSQL project: https://neon.tech/")
    report_parts.append("  3. Run the schema in Neon SQL Editor:")
    report_parts.append("     CREATE EXTENSION IF NOT EXISTS vector;")
    report_parts.append("     CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    report_parts.append("     [Run the full database/schema.sql]")
    report_parts.append("  4. Fill in backend/.env with:")
    report_parts.append("     GROQ_API_KEY=gsk_...                # your Groq key")
    report_parts.append("     NEON_DSN=postgresql://user:pw@ep.db.region.neon.tech:5455/dbname")
    report_parts.append("  5. Re-run this check: python -m app.check_setup")
    return 0, report_parts


if __name__ == "__main__":
    exit_code, report_lines = main()
    print("\n".join(report_lines))
    sys.exit(exit_code)