import base64
import uuid
from collections import defaultdict
from pathlib import Path
from time import time
from datetime import datetime
from typing import Dict, List, Literal
from urllib.parse import urljoin
import yaml

import markdown
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from github import Github, GithubException
from pydantic import ValidationError
from slugify import slugify

from auth import verify_auth_token
from utils import load_config, mf2_to_jekyll
from schemas import Config, MicropubConfigResponse, MicropubRequest, GithubFileResponse

app = FastAPI()

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


@app.post("/media", response_model_exclude_none=True, status_code=201)
async def media_endpoint(
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
    try:
        github_response_dict = repo.create_file(
            path=f"{config.media_dir}/{filename}",
            message=f"Upload {config.media_dir}/{filename}",
            content=encoded,
        )
        github_response = GithubFileResponse.model_validate(github_response_dict, from_attributes=True)
    except (ValidationError, GithubException) as e:
        raise HTTPException(status_code=500, detail={"error": "github_response_invalid", "error_description": f"Received an unexpected response from GitHub: {e}"})
    
    github_media_url = urljoin(str(config.site_url), f"/{github_response.content.path}")
    return JSONResponse(
        status_code=201,
        content={"url": github_media_url},
        headers={"Location": github_media_url},
    )


def mf2_form_to_json(form: Form) -> Dict:
    grouped = defaultdict(list)
    mf2_type = "entry"
    for key, value in form.multi_items():
        if key == "h":
            mf2_type = value
        else:
            grouped[key].append(value)
    
    response ={
        "type": [f"h-{mf2_type}"],
        "properties": dict(grouped),
    }
    return response


async def parse_micropub_request(
    request: Request,
) -> MicropubRequest:
    if request.headers.get("Content-Type", "").startswith("application/json"):
        response_json = await request.json()
        return MicropubRequest.model_validate(response_json)
    elif request.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        response_json = mf2_form_to_json(form)
        return MicropubRequest.model_validate(response_json)
    else:
        raise HTTPException(status_code=400, detail={"error": "invalid_content_type", "error_description": "Unsupported Content-Type"})

@app.post("/micropub", response_model_exclude_none=True, status_code=202)
async def micropub_endpoint(
    github: Github = Depends(github_login),
    token_data: Dict = Depends(verify_auth_token),
    config: Config = Depends(load_config),
    micropub_request: Dict = Depends(parse_micropub_request)
):
    print("Received micropub request:", micropub_request)
    
    # Convert mf2 to frontmatter and mp commands
    micropub_request_dict = micropub_request.model_dump()
    frontmatter, content = mf2_to_jekyll(micropub_request_dict)
    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    # Determine filename based on timestamp and slugified title or URL
    timestamp = int(time())
    dt = datetime.fromtimestamp(timestamp)
    if frontmatter.get("title"):
        slug = slugify(frontmatter["title"])
        filename = f"{dt:%Y-%m-%d}-{slug}.md"
        dirname = config.article_dir
        post_url = urljoin(str(config.site_url), config.article_dir.lstrip("_") + f"/{dt:%Y}/{dt:%m}/{dt:%d}/{slug}")
    else:
        slug = slugify(str(timestamp))
        filename = f"{slug}.md"
        dirname = config.note_dir
        post_url = urljoin(str(config.site_url), config.note_dir.lstrip("_") + f"/{dt:%Y}/{dt:%m}/{dt:%d}/{slug}")

    # Write to GitHub
    filecontent = f"---\n{frontmatter_yaml}---\n{content}"
    repo = github.get_user().get_repo(config.github_repo)
    try:
        github_response_dict = repo.create_file(
            path=f"{dirname}/{filename}",
            message=f"Create {dirname}/{filename}",
            content=filecontent,
        )
        github_response = GithubFileResponse.model_validate(github_response_dict, from_attributes=True)
    except (ValidationError, GithubException) as e:
        raise HTTPException(status_code=500, detail={"error": "github_response_invalid", "error_description": "Received an unexpected response from GitHub"})

    return JSONResponse(
        status_code=202,
        content={"url": post_url},
        headers={"Location": post_url},
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
