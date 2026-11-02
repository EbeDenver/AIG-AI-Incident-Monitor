"""Export Package Management and Delivery Routes.

Implements Phase 8C web routes:
- List generated export packages (GET /packages)
- Inspect export package manifest and file metadata (GET /packages/{export_id})
- Export dossier into managed publication/review package (POST /dossiers/{dossier_id}/export)
- Authenticated and authorized file downloads with path traversal defenses (GET /packages/{export_id}/download/{filename})
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.renderers.exporter import (
    DEFAULT_EXPORT_DIR,
    EditorialDossierExporter,
)
from ai_incident_monitor.editorial.renderers.manifest import EditorialExportManifest
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from ai_incident_monitor.ui.auth import SESSION_COOKIE_NAME, ServerSessionManager

router = APIRouter(tags=["editorial-packages"])

SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
SAFE_EXPORT_ID_PATTERN = re.compile(r"^exp_[a-zA-Z0-9]+$")


def _get_authenticated_session(request: Request) -> Any:
    """Validate and return active server-side session or None."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return sess_mgr.get_session(session_cookie)


def _verify_csrf(request: Request, candidate_csrf: Optional[str]) -> bool:
    """Validate candidate CSRF token against session token."""
    session = _get_authenticated_session(request)
    if not session:
        return False
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    return sess_mgr.validate_csrf(session, candidate_csrf)


def get_export_dir(request: Request) -> Path:
    """Resolve and return absolute path to export directory."""
    repo_root: Path = getattr(request.app.state, "repo_root", Path("."))
    out_dir = repo_root / DEFAULT_EXPORT_DIR
    return out_dir.resolve()


def load_all_packages(export_dir: Path) -> list[EditorialExportManifest]:
    """Scan and parse all package manifests in the export directory."""
    if not export_dir.exists() or not export_dir.is_dir():
        return []
    manifests: list[EditorialExportManifest] = []
    for mf in export_dir.glob("*.manifest.json"):
        if mf.is_symlink() or os.path.islink(str(mf)):
            continue
        try:
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
                m = EditorialExportManifest.model_validate(data)
                manifests.append(m)
        except Exception:
            continue
    manifests.sort(key=lambda m: m.exported_at_utc, reverse=True)
    return manifests


def find_package_by_export_id(
    export_dir: Path, export_id: str
) -> Optional[tuple[EditorialExportManifest, Path]]:
    """Locate package manifest by export_id."""
    if not export_dir.exists() or not export_dir.is_dir():
        return None
    for mf in export_dir.glob("*.manifest.json"):
        if mf.is_symlink() or os.path.islink(str(mf)):
            continue
        try:
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("export_id") == export_id:
                    return EditorialExportManifest.model_validate(data), mf
        except Exception:
            continue
    return None


def get_package_files(
    export_dir: Path, manifest: EditorialExportManifest, manifest_path: Path
) -> list[dict[str, Any]]:
    """Enumerate all existing files associated with an export package."""
    files: list[dict[str, Any]] = []
    base_stem = (
        manifest_path.name[: -len(".manifest.json")]
        if manifest_path.name.endswith(".manifest.json")
        else ""
    )

    candidate_names = [manifest.output_filename, manifest_path.name]
    if base_stem:
        candidate_names.extend([f"{base_stem}.md", f"{base_stem}.json"])

    seen: set[str] = set()
    for name in candidate_names:
        if name in seen:
            continue
        seen.add(name)
        fpath = export_dir / name
        if fpath.exists() and fpath.is_file() and not fpath.is_symlink():
            stat = fpath.stat()
            sha256 = ""
            try:
                with open(fpath, "rb") as fp:
                    sha256 = hashlib.sha256(fp.read()).hexdigest()
            except Exception:
                pass
            files.append({
                "filename": name,
                "size_bytes": stat.st_size,
                "file_hash": sha256,
                "is_manifest": name.endswith(".manifest.json"),
            })
    return files


@router.get("/packages", response_class=HTMLResponse)
async def list_packages(
    request: Request,
    dossier_id: Optional[str] = Query(default=None),
    purpose: Optional[str] = Query(default=None),
) -> Response:
    """List all generated export packages with filtering and metadata."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    export_dir = get_export_dir(request)
    all_packages = load_all_packages(export_dir)

    filtered = all_packages
    if dossier_id and dossier_id.strip():
        filtered = [p for p in filtered if p.dossier_id == dossier_id.strip()]
    if purpose and purpose.strip():
        filtered = [p for p in filtered if p.artifact_purpose.value == purpose.strip()]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="packages/list.html",
        context={
            "session": session,
            "packages": filtered,
            "total_packages": len(all_packages),
            "filter_dossier_id": dossier_id or "",
            "filter_purpose": purpose or "",
            "purposes": [p.value for p in EditorialArtifactPurpose],
        },
    )


@router.get("/packages/{export_id}", response_class=HTMLResponse)
async def package_detail(request: Request, export_id: str) -> Response:
    """Inspect metadata, provenance, and files for a specific package."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not SAFE_EXPORT_ID_PATTERN.match(export_id):
        raise HTTPException(status_code=400, detail="Invalid export ID format.")

    export_dir = get_export_dir(request)
    pkg = find_package_by_export_id(export_dir, export_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Export package '{export_id}' not found.")

    manifest, manifest_path = pkg
    files = get_package_files(export_dir, manifest, manifest_path)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="packages/detail.html",
        context={
            "session": session,
            "manifest": manifest,
            "files": files,
            "manifest_filename": manifest_path.name,
        },
    )


@router.get("/packages/{export_id}/download/{filename}")
async def download_package_file(
    request: Request, export_id: str, filename: str
) -> Response:
    """Securely download an artifact file belonging to an export package."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # 1. Parameter format validations
    if not SAFE_EXPORT_ID_PATTERN.match(export_id):
        raise HTTPException(status_code=400, detail="Invalid export ID format.")
    if not SAFE_FILENAME_PATTERN.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename format or path traversal attempt.")

    # 2. Locate package
    export_dir = get_export_dir(request)
    pkg = find_package_by_export_id(export_dir, export_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Export package '{export_id}' not found.")

    manifest, manifest_path = pkg
    package_files = get_package_files(export_dir, manifest, manifest_path)
    allowed_filenames = {f["filename"] for f in package_files}

    if filename not in allowed_filenames:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' does not belong to export package '{export_id}'.",
        )

    # 3. Path resolution & confinement defense
    target_path = (export_dir / filename).resolve()
    if not target_path.is_relative_to(export_dir):
        raise HTTPException(status_code=403, detail="Forbidden: Path traversal outside export directory.")
    if target_path.is_symlink() or os.path.islink(str(target_path)):
        raise HTTPException(status_code=403, detail="Forbidden: Symlinked files cannot be downloaded.")
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found on disk.")

    # 4. MIME type selection
    media_type = "application/octet-stream"
    if filename.endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    elif filename.endswith(".json"):
        media_type = "application/json; charset=utf-8"

    return FileResponse(
        path=target_path,
        filename=filename,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/dossiers/{dossier_id}/export", response_class=HTMLResponse)
async def export_dossier_route(
    request: Request,
    dossier_id: str,
    profile: str = Form(default=EditorialPresentationProfile.DEEP_DIVE_DOSSIER.value),
    format: str = Form(default=EditorialExportFormat.MARKDOWN.value),
    purpose: str = Form(default=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY.value),
    overwrite: bool = Form(default=False),
    csrf_token: Optional[str] = Form(default=None),
) -> Response:
    """Create an export package for an editorial dossier under domain safety rules."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    # Validate enums
    try:
        profile_enum = EditorialPresentationProfile(profile.strip().upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid presentation profile '{profile}'.")

    try:
        format_enum = EditorialExportFormat(format.strip().upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid export format '{format}'.")

    try:
        purpose_enum = EditorialArtifactPurpose(purpose.strip().upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact purpose '{purpose}'.")

    engine = request.app.state.db_engine
    export_dir = get_export_dir(request)

    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        dossier = repo.get_dossier(dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")

        exporter = EditorialDossierExporter(repo)
        try:
            result = exporter.export(
                dossier_id=dossier_id,
                export_format=format_enum,
                profile=profile_enum,
                purpose=purpose_enum,
                output_dir=str(export_dir),
                overwrite=overwrite,
                dry_run=False,
                actor_id=session.actor_id,
                is_human=session.is_human,
                actor_role=session.role,
            )
            db_session.commit()
            export_id = result.export_id
        except FileExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Package file collision: {exc}. Enable overwrite to replace.",
            )
        except (ValueError, ConstitutionalViolationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    return RedirectResponse(
        url=f"/packages/{export_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
