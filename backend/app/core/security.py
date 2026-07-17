from fastapi import Header, HTTPException, status
from app.core.config import get_settings


async def verify_prompt_secret(
    x_prompt_secret: str = Header(..., description="Secret key to access prompt data")
) -> str:
    """
    Dependency: validates X-Prompt-Secret header before returning prompt.
    Replace with JWT / OAuth2 for production.
    """
    settings = get_settings()
    if x_prompt_secret != settings.PROMPT_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing prompt secret.",
            headers={"WWW-Authenticate": "X-Prompt-Secret"},
        )
    return x_prompt_secret