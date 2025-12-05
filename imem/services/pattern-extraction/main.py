"""Pattern Extraction Service - EPIC 7

Cloud service extracting pattern layers from implementation chunks.
Uses tiny LLM (Llama-3.2-3B via OpenRouter) for abstraction.

Deploy: modal deploy main.py
Local: uvicorn main:app --reload
"""

import os
import asyncio
import logging
from typing import List, Optional
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/llama-3.2-3b-instruct"
MAX_CONCURRENT = 50  # Bounded concurrency for rate limiting

# Pattern extraction prompt (from spec)
EXTRACTION_PROMPT = """Extract the reusable pattern from this implementation chunk.

Rules:
1. Remove project-specific details (file paths, class names, variable names, dates, UUIDs)
2. Keep the architectural insight and decision rationale
3. Generalize to be applicable across projects
4. Preserve the structure (headers, bullet points)
5. Be concise - pattern should be ~30-50% shorter than original

Output the pattern layer only, no commentary.

Implementation chunk:
{content}"""


# ============================================================================
# Models
# ============================================================================

class ChunkInput(BaseModel):
    """Single chunk for pattern extraction"""
    id: str = Field(..., description="Chunk ID for correlation")
    content: str = Field(..., description="Implementation content to abstract")


class ExtractionRequest(BaseModel):
    """Batch extraction request"""
    chunks: List[ChunkInput] = Field(..., min_length=1, max_length=100)


class PatternOutput(BaseModel):
    """Single pattern extraction result"""
    id: str
    pattern_layer: str
    error: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Batch extraction response"""
    patterns: List[PatternOutput]
    model: str
    chunks_processed: int


# ============================================================================
# LLM Client
# ============================================================================

class LLMClient:
    """Async client for OpenRouter LLM gateway"""

    def __init__(
        self,
        api_key: str,
        api_url: str = OPENROUTER_API_URL,
        model: str = DEFAULT_MODEL,
        max_concurrent: int = MAX_CONCURRENT,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def extract_pattern(self, chunk_id: str, content: str) -> PatternOutput:
        """Extract pattern from single chunk with bounded concurrency"""
        async with self.semaphore:
            try:
                session = await self.get_session()
                prompt = EXTRACTION_PROMPT.format(content=content[:8000])  # Limit input

                async with session.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                        "temperature": 0.3,  # Lower temp for consistency
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(f"LLM error for {chunk_id}: {response.status} - {error_text[:200]}")
                        return PatternOutput(id=chunk_id, pattern_layer="", error=f"LLM error: {response.status}")

                    data = await response.json()
                    pattern = data["choices"][0]["message"]["content"].strip()
                    return PatternOutput(id=chunk_id, pattern_layer=pattern)

            except asyncio.TimeoutError:
                logger.warning(f"Timeout extracting pattern for {chunk_id}")
                return PatternOutput(id=chunk_id, pattern_layer="", error="Timeout")
            except Exception as e:
                logger.error(f"Error extracting pattern for {chunk_id}: {e}")
                return PatternOutput(id=chunk_id, pattern_layer="", error=str(e))

    async def extract_batch(self, chunks: List[ChunkInput]) -> List[PatternOutput]:
        """Extract patterns from batch with parallel execution"""
        tasks = [self.extract_pattern(c.id, c.content) for c in chunks]
        return await asyncio.gather(*tasks)


# ============================================================================
# FastAPI App
# ============================================================================

# Global LLM client
llm_client: Optional[LLMClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle management"""
    global llm_client

    # Startup
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set - LLM calls will fail")

    model = os.environ.get("PATTERN_MODEL", DEFAULT_MODEL)
    llm_client = LLMClient(api_key=api_key, model=model)
    logger.info(f"Pattern extraction service started with model: {model}")

    yield

    # Shutdown
    if llm_client:
        await llm_client.close()
    logger.info("Pattern extraction service stopped")


app = FastAPI(
    title="Pattern Extraction Service",
    description="EPIC 7 - Extract pattern layers from implementation chunks",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model": os.environ.get("PATTERN_MODEL", DEFAULT_MODEL),
    }


@app.post("/v1/extract-patterns", response_model=ExtractionResponse)
async def extract_patterns(request: ExtractionRequest):
    """Extract pattern layers from implementation chunks

    Accepts batch of chunks, returns abstracted pattern layers.
    Uses bounded concurrency (50) to prevent rate limiting.

    Benchmark: ~8.5 chunks/sec @ 50 concurrent
    """
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    # Validate minimum content length
    valid_chunks = [c for c in request.chunks if len(c.content) > 50]
    if not valid_chunks:
        raise HTTPException(status_code=400, detail="All chunks too short (min 50 chars)")

    # Extract patterns in parallel
    patterns = await llm_client.extract_batch(valid_chunks)

    # Log results
    success_count = sum(1 for p in patterns if not p.error)
    logger.info(f"Extracted {success_count}/{len(valid_chunks)} patterns successfully")

    return ExtractionResponse(
        patterns=patterns,
        model=llm_client.model,
        chunks_processed=len(valid_chunks),
    )


# ============================================================================
# Modal Deployment (optional)
# ============================================================================

# Uncomment for Modal deployment:
# import modal
#
# stub = modal.Stub("pattern-extraction")
#
# @stub.function(
#     secret=modal.Secret.from_name("openrouter"),
#     keep_warm=1,
# )
# @modal.asgi_app()
# def modal_app():
#     return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
