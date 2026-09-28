"""Uvicorn entrypoint: ``python -m law_rag.api.main``.

The process binds to a local address by default (LAN/offline deployment) and reads
non-secret settings from the environment (``docs/14``). When ``LAW_RAG_CONFIG_FILE``
is set, the container is wired from that bootstrap file: users, roles, collections,
tokens and the ingestion pipeline. Without it the API starts with an empty identity
registry, so every request is rejected — the fail-closed default of ADR-010.
"""

from __future__ import annotations

import logging
import os

from .app import create_app
from .bootstrap import build_container, config_from_env, print_generated_tokens

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger(__name__)


def build_app():
    """Create the ASGI app, wiring the deployment bootstrap when configured."""
    config = config_from_env()
    if config is None:
        LOGGER.warning(
            "LAW_RAG_CONFIG_FILE is not set: starting without users, collections or "
            "ingestion pipeline (all authenticated requests will be rejected)."
        )
        return create_app()
    result = build_container(config)
    print_generated_tokens(result)
    return create_app(result.container)


app = build_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("LAW_RAG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LAW_RAG_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
