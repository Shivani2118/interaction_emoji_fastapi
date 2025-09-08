# app.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import datetime
import re
import random

# ----- Database setup (SQLite) -----
DATABASE_URL = "sqlite:///./emoji.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# ----- ORM model -----


class EmojiMapping(Base):
    __tablename__ = "emoji_mappings"
    id = Column(Integer, primary_key=True, index=True)
    emoji = Column(String, unique=True, index=True, nullable=False)
    unicode_seq = Column(String, nullable=False)
    movie_name = Column(String, nullable=False)
    hint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# ----- Pydantic schemas (only the fields you asked for) -----


class RandomEmojiOut(BaseModel):
    emoji: str
    unicode_seq: str
    movie_name: str

    class Config:
        orm_mode = True

# ----- Utility functions -----


def emoji_to_unicode_seq(s: str) -> str:
    """Convert each codepoint to U+XXXX tokens (handles multi-codepoint sequences)."""
    return " ".join(f"U+{ord(ch):04X}" for ch in s)

# ----- Dependency for DB session -----


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----- FastAPI app -----
app = FastAPI(title="Emoji Movie Random API (GET-only, no id required)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables & seed sample data if DB empty


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = db.query(EmojiMapping).count()
        if count == 0:
            samples = [
                ("🎥🕵️‍♂️", "Sherlock Holmes", "A famous detective"),
                ("🚀🌕", "First Man", "Space and the moon"),
                ("🧙‍♂️🧝‍♀️", "The Lord of the Rings", "A ring and a long journey"),
                ("😄🎬", "The Big Smile", "A big grin + movie")
            ]
            for emoji, movie, hint in samples:
                seq = emoji_to_unicode_seq(emoji)
                mapping = EmojiMapping(
                    emoji=emoji, unicode_seq=seq, movie_name=movie, hint=hint
                )
                db.add(mapping)
            db.commit()
    finally:
        db.close()

# ----- GET Endpoints (no id required) -----


@app.get("/emojis", response_model=RandomEmojiOut, summary="Get one random mapping (emoji, unicode_seq, movie_name)")
def get_random_mapping(db: Session = Depends(get_db)):
    """
    Returns one random mapping. Frontend should call this endpoint to get
    a random emoji + movie_name + unicode sequence — no id required.
    """
    # fetch only the columns we need to reduce memory overhead
    items = db.query(EmojiMapping.emoji, EmojiMapping.unicode_seq,
                     EmojiMapping.movie_name).all()
    if not items:
        raise HTTPException(
            status_code=404, detail="No emoji mappings available")
    # each item is a tuple (emoji, unicode_seq, movie_name)
    emoji_val, seq_val, movie_val = random.choice(items)
    return {"emoji": emoji_val, "unicode_seq": seq_val, "movie_name": movie_val}


@app.get("/emojis/all", response_model=List[RandomEmojiOut], summary="List all mappings (emoji, unicode_seq, movie_name)")
def list_mappings(db: Session = Depends(get_db)):
    rows = db.query(EmojiMapping.emoji, EmojiMapping.unicode_seq,
                    EmojiMapping.movie_name).order_by(EmojiMapping.id).all()
    return [{"emoji": r[0], "unicode_seq": r[1], "movie_name": r[2]} for r in rows]
