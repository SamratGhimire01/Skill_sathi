from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

load_dotenv()

DB_HOSTNAME = os.getenv("DATABASE_HOSTNAME")
DB_PORT = os.getenv("DATABASE_PORT")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")
DB_NAME = os.getenv("DATABASE_NAME")
DB_USERNAME = os.getenv("DATABASE_USERNAME")

if not all([DB_HOSTNAME, DB_PORT, DB_PASSWORD, DB_NAME, DB_USERNAME]):
    raise ValueError("❌ Missing database variables in .env file.")
# CRITICAL FIX: If Docker is running (based on presence of DOCKER_ENV var), use the service name 'db'
if os.getenv('DOCKER_ENV') == 'true':
    DB_HOSTNAME = 'db'
# Handle special characters in password
encoded_password = quote_plus(DB_PASSWORD)

SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{DB_USERNAME}:{encoded_password}@{DB_HOSTNAME}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()