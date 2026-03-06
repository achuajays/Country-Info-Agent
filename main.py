"""FastAPI backend for the Country Information AI Agent.

Endpoints:
    GET  /              → Serves the chat UI
    POST /api/ask       → Invokes the LangGraph agent
    GET  /api/health    → Health check
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.graph import agent

# Load .env before anything else
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)
logger = logging.getLogger("country_agent")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Country Information AI Agent",
    description="Ask questions about any country in the world.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    country: str = ""
    flag_url: str = ""
    error: bool = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def serve_ui():
    """Serve the chat frontend."""
    return FileResponse("static/index.html")


@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """Invoke the LangGraph agent and return the answer."""
    question = req.question.strip()
    logger.info("Question: %s", question)

    if not question:
        return AskResponse(
            answer="Please ask a question about a country!",
            error=True,
        )

    try:
        result = await agent.ainvoke({
            "question": question,
            "country": "",
            "fields": [],
            "api_data": None,
            "flag_url": "",
            "error": None,
            "answer": "",
        })

        has_error = bool(result.get("error"))

        return AskResponse(
            answer=result.get("answer", "Sorry, I couldn't generate an answer."),
            country=result.get("country", ""),
            flag_url=result.get("flag_url", ""),
            error=has_error,
        )

    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        return AskResponse(
            answer="An unexpected error occurred. Please try again.",
            error=True,
        )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "country-agent"}
