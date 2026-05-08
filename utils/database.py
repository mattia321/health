from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class HealthRecord(Base):
    __tablename__ = 'health_records'
    id = Column(Integer, primary_key=True)
    type = Column(String, index=True)
    sourceName = Column(String)
    startDate = Column(DateTime, index=True)
    endDate = Column(DateTime)
    value = Column(Float)
    unit = Column(String)

def get_engine(db_path='sqlite:///health_data.db'):
    return create_engine(db_path)

def create_tables(engine):
    Base.metadata.create_all(engine)

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
