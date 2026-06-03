from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./store.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class DBEvent(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True)
    camera_id = Column(String)
    visitor_id = Column(String, index=True)
    event_type = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    zone_id = Column(String, nullable=True)
    dwell_ms = Column(Integer, nullable=True)
    is_staff = Column(Boolean, default=False)
    confidence = Column(Float)
    metadata_json = Column(JSON, nullable=True)

class DBPosTransaction(Base):
    __tablename__ = "pos_transactions"

    transaction_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    basket_value_inr = Column(Float)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
