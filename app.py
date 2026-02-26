from pathlib import Path
from typing import List, Literal, Dict

import markdown
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from github import Github
from pydantic import BaseModel, Field, HttpUrl, ValidationError

import base64
from config import Config, SyndicationEndpoint, load_config
from auth import verify_auth_token
import uuid
from urllib.parse import urljoin
from time import time

app = FastAPI()

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
    token_data: Dict = Depends(verify_auth_token),
    config: Config = Depends(load_config),
) -> MicropubConfigResponse:
    if q == "config":
        return MicropubConfigResponse(
            me=config.me,
            token_endpoint=config.token_endpoint,
            media_endpoint=urljoin(str(config.site_url), "/media"),
            syndicate_to=[endpoint.model_dump() for endpoint in config.syndicate_to] if config.syndicate_to else None,
        )
    elif q == "syndicate-to":
        return MicropubConfigResponse(
            syndicate_to=[endpoint.model_dump() for endpoint in config.syndicate_to] if config.syndicate_to else None
        )
    elif q == "media-endpoint":
        return MicropubConfigResponse(media_endpoint=urljoin(str(config.site_url), "/media"))
    elif q == "source":
        raise HTTPException(
            status_code=400, detail={"error": "unsupported_query", "error_description": f"Query '{q}' is not yet supported"}
        )

async def github_login(config: Config = Depends(load_config)):
    try:
        return Github(config.github_token)
    except Exception:
        raise HTTPException(status_code=500, detail={"error": "github_login_failed", "error_description": "Failed to authenticate with GitHub"})

class GithubFileResponse(BaseModel):
    class ContentFile(BaseModel):
        path: str
    class Commit(BaseModel):
        sha: str

    content: ContentFile
    commit: Commit

@app.post("/media", response_model_exclude_none=True)
async def media_endpoint(
    response: Response,
    github: Github = Depends(github_login),
    token_data: Dict = Depends(verify_auth_token),
    config: Config = Depends(load_config),
    file: UploadFile = File(..., description="Media file to upload"),
):    
    # Filename should be timestamp + truncated UUID
    timestamp = int(time())
    uuid_str = str(uuid.uuid4())[:8]
    filetype = Path(file.filename).suffix
    filename = f"{timestamp}_{uuid_str}{filetype}"

    repo = github.get_user().get_repo(config.github_repo)
    contents = await file.read()
    encoded = base64.b64encode(contents).decode("utf-8")
    github_response_dict = repo.create_file(
        path=f"{config.media_dir}/{filename}",
        message=f"Upload {config.media_dir}/{filename}",
        content=encoded,
    )
    try:
        github_response = GithubFileResponse.model_validate(github_response_dict, from_attributes=True)
    except ValidationError:
        raise HTTPException(status_code=500, detail={"error": "github_response_invalid", "error_description": "Received an unexpected response from GitHub"})
    
    github_media_url = urljoin(str(config.site_url), f"/{github_response.content.path}")
    return JSONResponse(
        status_code=201,
        content={"url": github_media_url},
        headers={"Location": github_media_url},
    )

templates = Jinja2Templates(directory="templates")
md = Path("README.md").read_text()
html_content = markdown.markdown(md, extensions=["fenced_code"])


@app.get("/")
async def home(request: Request):
    response = templates.TemplateResponse(
        "index.html",
        {"request": request, "content": html_content},
    )
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")
