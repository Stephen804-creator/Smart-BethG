from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import require_role

router = APIRouter(prefix="/admin/training-export", tags=["admin"])

# Conversation data must not be exported for model training until explicit,
# recorded, revocable user consent exists. Admin authorization alone is not
# user consent. Keep the endpoints fail-closed until that consent system ships.


def _require_training_consent_system():
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Training export is temporarily disabled until explicit user "
            "consent and withdrawal controls are implemented."
        ),
    )


@router.get("/preview")
def preview(user=Depends(require_role("admin"))):
    _require_training_consent_system()


@router.get("")
def export(user=Depends(require_role("admin"))):
    _require_training_consent_system()
