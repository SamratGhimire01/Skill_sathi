from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models
from routers import auth, companies, workers, certificates, verification, admin, dashboard, support

# Create tables if they don't exist (Useful for dev, but we are using schema.sql)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SkillSathi API")

origins = ["*"] # Adjust for production

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(workers.router)
app.include_router(certificates.router)
app.include_router(verification.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(support.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "SkillSathi Backend is Running 🚀"}