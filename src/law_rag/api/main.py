"""Uvicorn entrypoint: ``python -m law_rag.api.main``.

The process binds to a local address by default (LAN/offline deployment) and reads
non-secret settings from the environment. No credentials are read from here: users
and tokens are provisioned through the application container by deployment code.
"""

from __future__ import annotations

import os

from .app import create_app

app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("LAW_RAG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LAW_RAG_API_PORT", "8000"))
    uvicorn.run("law_rag.api.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
