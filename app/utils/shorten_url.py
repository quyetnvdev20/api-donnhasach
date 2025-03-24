from fastapi import HTTPException
from app.config import settings
import httpx
from fastapi import status
import logging
logger = logging.getLogger(__name__)

async def generate_shorten_url(url: str) -> str:
  """
  url: url to shorten
  """
  async with httpx.AsyncClient() as client:
    response = await client.post(
      f"{settings.SHORTEN_URL_API_URL}/shorten",
      json={"destination": url},
      headers={
        "x-access-token": settings.SHORTEN_URL_API_KEY,
        "Content-Type": "application/json"
      }
    )
    if response.status_code == 200:
      return response.json()["short_url"]
    else:
      logger.error(f"Failed to shorten url: {response.json()}")
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to shorten url")
