"""FastAPI application factory."""

from fastapi import FastAPI

from f1_history_agent import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="F1 History Agent", version=__version__)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
