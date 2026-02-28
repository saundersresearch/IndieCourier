import base64
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import time
from typing import Dict, List, Literal
from urllib.parse import urljoin

import markdown
import mf2py
import yaml
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from github import Github, GithubException
from parse import parse
from pydantic import ValidationError
from slugify import slugify

from auth import verify_auth_token
from schemas import Config, GithubFileResponse, MicropubActionRequest, MicropubConfigResponse, MicropubRequest
from utils import get_datetime, is_note, load_config, mf2_to_jekyll

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
            status_code=400,
            detail={"error": "unsupported_query", "error_description": f"Query '{q}' is not yet supported"},
        )


async def github_login(config: Config = Depends(load_config)):
    try:
        return Github(config.github_token)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"error": "github_login_failed", "error_description": "Failed to authenticate with GitHub"},
        )


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
        raise HTTPException(
            status_code=500,
            detail={
                "error": "github_error",
                "error_description": f"GitHub API error: {e}",
            },
        )

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

    response = {
        "type": [f"h-{mf2_type}"],
        "properties": dict(grouped),
    }
    return response


async def parse_micropub_request(
    request: Request,
) -> MicropubRequest | MicropubActionRequest:
    if request.headers.get("Content-Type", "").startswith("application/json"):
        response_json = await request.json()
        if "action" in response_json:
            return MicropubActionRequest.model_validate(response_json)
        else:
            return MicropubRequest.model_validate(response_json)
    elif request.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        if "action" in form:
            return MicropubActionRequest.model_validate(form)
        else:
            response_json = mf2_form_to_json(form)
            return MicropubRequest.model_validate(response_json)
    else:
        raise HTTPException(
            status_code=400, detail={"error": "invalid_content_type", "error_description": "Unsupported Content-Type"}
        )
    
def create_post(github: Github, micropub_request: MicropubRequest, config: Config) -> str:
    # Convert mf2 to frontmatter and mp commands
    micropub_request_dict = micropub_request.model_dump()
    frontmatter, content = mf2_to_jekyll(micropub_request_dict)
    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    # Determine filename based on timestamp and slugified title or URL
    timestamp = int(time())
    dt = datetime.fromtimestamp(timestamp)
    site_url = str(config.site_url).rstrip("/")
    if frontmatter.get("title"):
        slug = slugify(frontmatter["title"])
        filename = config.article_filepath_template.format(site_url=site_url, date=dt, slug=slug)
        post_url = config.article_url_template.format(site_url=site_url, date=dt, slug=slug)
    else:
        slug = slugify(str(timestamp))
        filename = config.note_filepath_template.format(site_url=site_url, date=dt, slug=slug)
        post_url = config.note_url_template.format(site_url=site_url, date=dt, slug=slug)

    # Write to GitHub
    filecontent = f"---\n{frontmatter_yaml}---\n{content}"
    repo = github.get_user().get_repo(config.github_repo)
    try:
        github_response_dict = repo.create_file(
            path=filename,
            message=f"Create {filename}",
            content=filecontent,
        )
        github_response = GithubFileResponse.model_validate(github_response_dict, from_attributes=True)
    except (ValidationError, GithubException) as e:
        raise HTTPException(status_code=500, detail={"error": "github_error", "error_description": f"GitHub API error: {e}"})

    return post_url

def delete_post(github: Github, url: str, config: Config) -> Response:
    url = str(url).rstrip("/")
    site_url = str(config.site_url).rstrip("/")
    if not url.startswith(site_url):
        raise HTTPException(status_code=400, detail={"error": "invalid_url", "error_description": "URL does not belong to this site"})
    
    # Parse the URL 
    mf2_parser = mf2py.parse(url=url)
    if is_note(mf2_parser):
        template_parsed = parse(config.note_url_template, url)
        path = config.note_filepath_template.format(site_url="", date=template_parsed["date"], slug=template_parsed["slug"])
        print(f"Identified as note: {url} -> {path}")
    else:
        template_parsed = parse(config.article_url_template, url)
        path = config.article_filepath_template.format(site_url="", date=template_parsed["date"], slug=template_parsed["slug"])
        print(f"Identified as article: {url} -> {path}")

    # Add published: false to frontmatter
    repo = github.get_user().get_repo(config.github_repo)
    try:
        contents = repo.get_contents(path)
        print(contents)
        file_content = contents.decoded_content.decode("utf-8")
        if "---" in file_content:
            frontmatter_raw, body = file_content.split("---", 2)[1:]
            frontmatter = yaml.safe_load(frontmatter_raw)
        else:
            frontmatter = {}
            body = file_content
            
        if "published" in frontmatter and frontmatter["published"] == False:
            raise HTTPException(status_code=400, detail={"error": "already_deleted", "error_description": "Post is already marked as deleted"})
        frontmatter["published"] = False
        new_frontmatter_raw = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        new_file_content = f"---\n{new_frontmatter_raw}---{body}"
        repo.update_file(
            path=path,
            message=f"Update {path} to delete",
            content=new_file_content,
            sha=contents.sha,
        )
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail={"error": "post_not_found", "error_description": "Could not find a post matching the provided URL"})
        else:
            raise HTTPException(status_code=500, detail={"error": "github_error", "error_description": f"GitHub API error: {e}"})
        
    return Response(status_code=204)

def undelete_post(github: Github, url: str, config: Config) -> Response:
    url = str(url).rstrip("/")
    site_url = str(config.site_url).rstrip("/")
    if not url.startswith(site_url):
        raise HTTPException(status_code=400, detail={"error": "invalid_url", "error_description": "URL does not belong to this site"})
    
    # Parse the URL 
    mf2_parser = mf2py.parse(url=url)
    if is_note(mf2_parser):
        template_parsed = parse(config.note_url_template, url)
        path = config.note_filepath_template.format(site_url="", date=template_parsed["date"], slug=template_parsed["slug"])
        print(f"Identified as note: {url} -> {path}")
    else:
        template_parsed = parse(config.article_url_template, url)
        path = config.article_filepath_template.format(site_url="", date=template_parsed["date"], slug=template_parsed["slug"])
        print(f"Identified as article: {url} -> {path}")

    # Remove published: false from frontmatter if it exists
    repo = github.get_user().get_repo(config.github_repo)
    try:
        contents = repo.get_contents(path)
        file_content = contents.decoded_content.decode("utf-8")
        if "---" in file_content:
            frontmatter_raw, body = file_content.split("---", 2)[1:]
            frontmatter = yaml.safe_load(frontmatter_raw)
        else:
            frontmatter = {}
            body = file_content
        
        if "published" not in frontmatter or frontmatter["published"] != False:
            raise HTTPException(status_code=400, detail={"error": "not_deleted", "error_description": "Post is not currently marked as deleted"})
        del frontmatter["published"]
        new_frontmatter_raw = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        new_file_content = f"---\n{new_frontmatter_raw}---{body}"
        repo.update_file(
            path=path,
            message=f"Update {path} to undelete",
            content=new_file_content,
            sha=contents.sha,
        )
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail={"error": "post_not_found", "error_description": "Could not find a post matching the provided URL"})
        else:
            raise HTTPException(status_code=500, detail={"error": "github_error", "error_description": f"GitHub API error: {e}"})
        
    return Response(status_code=204)

@app.post("/micropub", response_model_exclude_none=True, status_code=202)
async def micropub_endpoint(
    github: Github = Depends(github_login),
    token_data: Dict = Depends(verify_auth_token),
    config: Config = Depends(load_config),
    micropub_request: MicropubRequest | MicropubActionRequest = Depends(parse_micropub_request),
):
    print("Received request: ", micropub_request)
    if isinstance(micropub_request, MicropubActionRequest):
        if micropub_request.action == "delete":
            print(f"Received delete action for URL: {micropub_request.url}")
            response = delete_post(github, micropub_request.url, config)
            return response
        elif micropub_request.action == "undelete":
            print(f"Received undelete action for URL: {micropub_request.url}")
            response = undelete_post(github, micropub_request.url, config)
            return response
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "unsupported_action", "error_description": f"Action '{micropub_request.action}' is not yet supported"},
            )
    elif isinstance(micropub_request, MicropubRequest):
        print("Received micropub request:", micropub_request)
        post_url = create_post(github, micropub_request, config)
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
