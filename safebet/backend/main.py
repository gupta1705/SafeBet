from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import scan, stellar_scan
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SafeBet API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ],   # Vite dev server ports
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/api")
app.include_router(stellar_scan.router, prefix="/api")
