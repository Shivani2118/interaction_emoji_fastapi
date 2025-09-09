# app.py
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import random
from typing import List, Dict, Any, Optional

DATA_FILENAME = "emoji_data.json"

app = FastAPI(title="Unicode-to-Emoji API (JSON stores only unicode_seq)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",    # Angular dev server
        "http://127.0.0.1:4200"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of full records loaded from JSON.
# Each record will have keys: unicode_seq (str), movie_name (str), hint (str), emoji (computed str)
_EMOJI_ITEMS: List[Dict[str, Any]] = []


def unicode_seq_to_emoji(seq: str) -> str:
    """
    Convert a sequence like "U+1F680 U+1F315" or "1F680 1F315"
    into the corresponding emoji characters string.
    Handles spaces between codepoints and ignores empty tokens.
    """
    if not seq or not isinstance(seq, str):
        return ""
    parts = seq.split()
    chars = []
    for token in parts:
        token = token.strip()
        if not token:
            continue
        # allow formats: U+1F680 or 1F680 or \\u1F680
        if token.upper().startswith("U+"):
            hexpart = token[2:]
        elif token.startswith("\\u") or token.startswith("\\U"):
            hexpart = token.lstrip("\\u").lstrip("\\U")
        else:
            hexpart = token
        # Remove potential non-hex characters
        hexpart = "".join(
            ch for ch in hexpart if ch in "0123456789abcdefABCDEF")
        if not hexpart:
            continue
        try:
            codepoint = int(hexpart, 16)
            chars.append(chr(codepoint))
        except Exception:
            # skip invalid codepoints silently
            continue
    return "".join(chars)


def load_data_from_file() -> None:
    """
    Load emoji_data.json from same directory. Expect a list of objects where each object has:
      - unicode_seq (string containing U+.... tokens or hex codepoints)
      - movie_name (string)
      - hint (string or omitted)
    The function computes the runtime 'emoji' field from unicode_seq and stores everything in _EMOJI_ITEMS.
    """
    global _EMOJI_ITEMS
    base = Path(__file__).resolve().parent
    data_path = base / DATA_FILENAME
    try:
        text = data_path.read_text(encoding="utf-8")
        loaded = json.loads(text)
        if not isinstance(loaded, list):
            raise ValueError("JSON root must be a list")
        items: List[Dict[str, Any]] = []
        for obj in loaded:
            if not isinstance(obj, dict):
                continue
            seq = obj.get("unicode_seq") or obj.get(
                "unicode") or obj.get("codepoints")
            movie_val = obj.get("movie_name") or obj.get("movie")
            hint_val = obj.get("hint") if ("hint" in obj) else ""
            if not seq or not movie_val:
                # skip records missing required fields
                continue
            emoji_chars = unicode_seq_to_emoji(seq)
            items.append({
                "unicode_seq": seq,
                "emoji": emoji_chars,
                "movie_name": movie_val,
                "hint": hint_val if hint_val is not None else ""
            })
        _EMOJI_ITEMS = items
    except Exception:
        # If file missing or corrupt, make empty list so endpoints return 404
        _EMOJI_ITEMS = []


@app.on_event("startup")
def startup_event():
    load_data_from_file()

# -----------------------
# Helpers
# -----------------------


def ensure_items():
    if not _EMOJI_ITEMS:
        raise HTTPException(
            status_code=404, detail="No emoji mappings available")


def as_plain_text(content: str) -> Response:
    return Response(content=content, media_type="text/plain; charset=utf-8")

# -----------------------
# Public endpoints (single random item)
# -----------------------


@app.get("/emoji", summary="Get emoji characters for one random unicode_seq (plain text)")
def random_emoji():
    """
    Returns the emoji characters converted from unicode_seq (plain text).
    Example response body: 🚀🌕
    Note: JSON file must contain only 'unicode_seq' (e.g. "U+1F680 U+1F315"), not emoji chars.
    """
    ensure_items()
    value = random.choice(_EMOJI_ITEMS)["emoji"]
    return as_plain_text(value)


@app.get("/movie", summary="Get one random movie name (plain text)")
def random_movie():
    """Return one random movie name as plain text (e.g. 'Sherlock Holmes')."""
    ensure_items()
    value = random.choice(_EMOJI_ITEMS)["movie_name"]
    return as_plain_text(value)


@app.get("/hint", summary="Get one random hint (plain text)")
def random_hint():
    """Return one random hint as plain text (may be empty string)."""
    ensure_items()
    value = random.choice(_EMOJI_ITEMS)["hint"] or ""
    return as_plain_text(value)
