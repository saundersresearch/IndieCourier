from typing import Dict

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import HttpUrl

from config import Config, load_config
from utils import is_url_equal

security = HTTPBearer(auto_error=False)

async def introspect_token(token: str, token_endpoint: HttpUrl, me: HttpUrl) -> Dict | None:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                str(token_endpoint), headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            if is_url_equal(data.get("me"), str(me)):
                return data
        except (httpx.HTTPError, ValueError):
            return None
        
async def verify_auth_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    config: Config = Depends(load_config),
) -> Dict:
    if not credentials:
        raise HTTPException(
            status_code=401, detail={"error": "unauthorized", "error_description": "Missing authorization token"}
        )

    token_data = await introspect_token(credentials.credentials, config.token_endpoint, config.me)
    if not token_data:
        raise HTTPException(
            status_code=403, detail={"error": "forbidden", "error_description": "Invalid authorization token"}
        )
    
    return token_data