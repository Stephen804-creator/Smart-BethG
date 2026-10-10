from fastapi import APIRouter, Depends

from api.dependencies import require_role
from services.training_export_service import TrainingExportService

router = APIRouter(prefix="/admin/training-export", tags=["admin"])


def get_training_export_service():
    return TrainingExportService()


@router.get("/preview")
def preview(
    since: str = None,
    until: str = None,
    user=Depends(require_role("admin")),
    service: TrainingExportService = Depends(get_training_export_service),
):
    """
    How many training examples would an export produce right now - a
    cheap check before pulling the full export.
    """
    return {"exportable_examples": service.count_exportable(since=since, until=until)}


@router.get("")
def export(
    since: str = None,
    until: str = None,
    limit: int = 1000,
    user=Depends(require_role("admin")),
    service: TrainingExportService = Depends(get_training_export_service),
):
    """
    Admin-only (see api.dependencies.require_role). Returns real
    conversation exchanges only - excludes honest-failure messages and
    synthesized tool/memory exchanges, excludes any user identity. This
    is a starting point for review before fine-tuning, not a
    ready-to-train dataset - see services/training_export_service.py.
    """
    return {"examples": service.export(since=since, until=until, limit=limit)}
