# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # <--- IMPORT THE MIDDLEWARE
from database import engine
import models
from routers import auth, companies, workers, certificates

# This command tells SQLAlchemy to create all the tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SkillSathi API")

# --- NEW: ADD CORS MIDDLEWARE ---
# This is the "permission slip" for the browser.
origins = [
    "*", # In production, you would replace this with your actual frontend domain
         # e.g., "http://www.skillsathi.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# Include the routers in our main app
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(workers.router)
app.include_router(certificates.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the SkillSathi API!"}