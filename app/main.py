
from fastapi import FastAPI

from app.core.config import settings
from app.api.v1.endpoints import health, projects, github

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

app.include_router(
    health.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    projects.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    github.router,
    prefix=settings.API_V1_PREFIX,
)