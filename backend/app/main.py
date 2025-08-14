from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from backend.app.api.steam import router as steam_router  # temporary Steam test endpoint
from backend.app.api.game_recommend import router as recommend_router

def create_app() -> FastAPI:
    app = FastAPI(title="Game Recommendation Engine - Backend")

    # Routers
    app.include_router(steam_router, prefix="/steam", tags=["steam"])  # test Steam search
    app.include_router(recommend_router, prefix="/recommend", tags=["recommend"])

    return app

app = create_app()