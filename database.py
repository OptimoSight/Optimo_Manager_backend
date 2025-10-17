import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://opti_manager:Optimo25Manager@localhost:5432/optimo_manager")
# DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/service_manager")


engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()