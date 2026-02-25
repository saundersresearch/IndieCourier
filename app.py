from pathlib import Path
from typing import List, Literal

import httpx
import markdown
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl

from config import Config, SyndicationEndpoint, load_config
from utils import is_url_equal

app = FastAPI()
security = HTTPBearer(auto_error=False)


async def verify_authorization_token(token: str, token_endpoint: HttpUrl, me: HttpUrl) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                str(token_endpoint), headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            return is_url_equal(data.get("me"), str(me))
        except (httpx.HTTPError, ValueError):
            return False


class MicropubConfigResponse(BaseModel):
    me: HttpUrl | None = None
    token_endpoint: HttpUrl | None = Field(None, alias="token-endpoint")
    media_endpoint: HttpUrl | None = Field(None, alias="media-endpoint")
    syndicate_to: List[SyndicationEndpoint] | None = Field(None, alias="syndicate-to")

    model_config = {
        "populate_by_name": True,
    }


@app.get("/micropub", response_model_exclude_none=True)
async def micropub_query(
    q: Literal["config", "syndicate-to", "media-endpoint", "source"] = Query(
        ..., description="The type of query to perform"
    ),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    config: Config = Depends(load_config),
) -> MicropubConfigResponse:
    if not credentials:
        raise HTTPException(
            status_code=401, detail={"error": "unauthorized", "error_description": "Missing authorization token"}
        )

    if not await verify_authorization_token(credentials.credentials, config.token_endpoint, config.me):
        raise HTTPException(
            status_code=403, detail={"error": "forbidden", "error_description": "Invalid authorization token"}
        )

    if q == "config":
        return MicropubConfigResponse(
            me=config.me,
            token_endpoint=config.token_endpoint,
            media_endpoint=config.media_endpoint,
            syndicate_to=[endpoint.model_dump() for endpoint in config.syndicate_to] if config.syndicate_to else None,
        )
    elif q == "syndicate-to":
        return MicropubConfigResponse(
            syndicate_to=[endpoint.model_dump() for endpoint in config.syndicate_to] if config.syndicate_to else None
        )
    elif q == "media-endpoint":
        return MicropubConfigResponse(media_endpoint=config.media_endpoint)
    elif q == "source":
        raise HTTPException(
            status_code=400, detail={"error": "unsupported_query", "error_description": f"Query '{q}' is not supported"}
        )


templates = Jinja2Templates(directory="templates")
md = Path("README.md").read_text()
html_content = markdown.markdown(md, extensions=["fenced_code"])


@app.get("/")
@app.head("/")
async def home(request: Request):
    response = templates.TemplateResponse(
        "base.html",
        {"request": request, "content": html_content},  # , headers={"Link": '</webmention>; rel="webmention"'}
    )
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")
