from fastapi import FastAPI
from app.api.analytics import router as analytics_router
from app.api.routes import router

app = FastAPI(title="Melbourne Tech Jobs", version="1.0.0",
              description="Melbourne tech job market data collected from Adzuna. Jobs by Adzuna.")
app.include_router(router)
app.include_router(analytics_router)
