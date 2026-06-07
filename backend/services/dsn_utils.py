"""
DSN host rewriting for containerized deployments.

Inside a container, a DSN whose host is localhost/127.0.0.1 resolves to the
container itself — not the user's machine — so connections to a database running
on the host fail with "connection refused". When REWRITE_LOCALHOST_DSN is enabled
(docker-compose sets it automatically), such hosts are transparently rewritten to
settings.DSN_LOCALHOST_REPLACEMENT (host.docker.internal on Docker Desktop), letting
users register datasources with the natural "localhost" host.
"""
import logging
import re
from urllib.parse import urlsplit, urlunsplit

from ..config import settings

logger = logging.getLogger(__name__)

# Hosts that mean "this machine" and must be redirected to the host from a container.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def maybe_rewrite_localhost_dsn(dsn: str) -> str:
    """Return the DSN with a localhost-style host swapped for the container host.

    No-op (returns the DSN unchanged) when:
      - REWRITE_LOCALHOST_DSN is disabled,
      - the DSN has no network host (e.g. sqlite:///path/to.db),
      - the host is not one of the localhost aliases,
      - or the DSN cannot be parsed.
    Userinfo (user:password), port, path, query and fragment are all preserved.
    """
    if not settings.REWRITE_LOCALHOST_DSN or not dsn:
        return dsn

    try:
        parts = urlsplit(dsn)
    except Exception:
        return dsn

    host = parts.hostname
    if not host or host.lower() not in _LOCAL_HOSTS:
        return dsn

    replacement = settings.DSN_LOCALHOST_REPLACEMENT

    # Rebuild netloc, preserving userinfo and port around the new host.
    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        userinfo += "@"

    netloc = f"{userinfo}{replacement}"
    if parts.port:
        netloc += f":{parts.port}"

    rewritten = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    logger.info("Rewrote host '%s' -> '%s' for container networking", host, replacement)
    return rewritten


# The same localhost->container-host rewrite applies to any URL (e.g. the LLM
# endpoint), not just database DSNs. Exposed under a clearer name for that use.
maybe_rewrite_localhost_url = maybe_rewrite_localhost_dsn


def pick_sqlserver_odbc_driver() -> str:
    """Return the best installed Microsoft SQL Server ODBC driver name.

    Prefers the newest "ODBC Driver NN for SQL Server" (18 > 17 > 13...) and falls
    back to the legacy "SQL Server" driver. Avoids hardcoding a version that may not
    be present in a given image/host."""
    try:
        import pyodbc
        installed = list(pyodbc.drivers())
    except Exception:
        return "ODBC Driver 18 for SQL Server"

    versioned = []
    for name in installed:
        m = re.match(r"ODBC Driver (\d+) for SQL Server", name)
        if m:
            versioned.append((int(m.group(1)), name))
    if versioned:
        return max(versioned)[1]
    if "SQL Server" in installed:
        return "SQL Server"
    return "ODBC Driver 18 for SQL Server"


def build_mssql_odbc_connstr(dsn: str) -> str:
    """Build a pyodbc connection string from an mssql:// DSN.

    Honours the localhost->container-host rewrite, picks the installed driver, and
    sets TrustServerCertificate=yes (Driver 18 defaults to Encrypt=yes, which rejects
    self-signed certs — common for containerized/dev SQL Server) so dev connections
    don't fail on TLS validation."""
    from urllib.parse import urlparse

    parsed = urlparse(maybe_rewrite_localhost_dsn(dsn))
    driver = pick_sqlserver_odbc_driver()
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={parsed.hostname or 'localhost'},{parsed.port or 1433};"
        f"DATABASE={parsed.path.lstrip('/') if parsed.path else 'master'};"
        f"UID={parsed.username};"
        f"PWD={parsed.password};"
        f"TrustServerCertificate=yes;"
    )
