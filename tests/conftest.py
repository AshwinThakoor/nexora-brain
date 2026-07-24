import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nexora_knowledge.database import Base
from nexora_knowledge import models

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session
