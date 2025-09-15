from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from backend.app.caches.rawg_metadata_cache import RAWGMetadataCache
from .api.steam import router as steam_router
from .api.game_recommend import router as recommend_router
from .services.aggregator import GameAggregator

load_dotenv()

# Initialise cache outside lifespan so it's accessible globally if needed
cache = RAWGMetadataCache()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup logic ---
    await cache.load_from_disk()  # prefetch RAWG metadata
    print("RAWG cache loaded")

    # Attach cache to app.state so NLQueryParser can access it
    app.state.rawg_metadata_cache = cache

    # Initialise aggregator and attach to app.state
    app.state.aggregator = await GameAggregator.create() # type: ignore[attr-defined]
    print("Aggregator initialised")

    yield  # main app runs here

    # --- Cleanup on shutdown ---
    await cache.save_to_disk()
    print("RAWG cache saved on shutdown")

def create_app() -> FastAPI:
    app = FastAPI(title="Game Recommendation Engine", lifespan=lifespan)

    # Routers
    app.include_router(steam_router, prefix="/steam", tags=["steam"])
    app.include_router(recommend_router, prefix="/recommend", tags=["recommend"])

    return app

app = create_app()