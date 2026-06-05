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
