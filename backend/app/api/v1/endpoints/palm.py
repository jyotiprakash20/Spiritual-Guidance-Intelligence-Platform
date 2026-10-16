from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.relational import Reading, User
from app.services.palm_service import palm_engine
from app.services.palm_interpretation import palm_interpretation_engine

router = APIRouter()


@router.post("/analyze")
async def analyze_palm(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze an uploaded palm image, generate interpretation, and save the reading."""

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    try:
        result = palm_engine.process_image(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Palm image analysis failed. Please try again.",
        )

    if not result.get("detected"):
        raise HTTPException(
            status_code=422,
            detail=result.get(
                "message",
                "Could not detect a palm. Please upload a clear palm image.",
            ),
        )

    features = result.get("features")

    if not isinstance(features, dict):
        raise HTTPException(
            status_code=422,
            detail="Palm features could not be extracted.",
        )

    # The palm service is the vision layer.
    # The interpretation service is the symbolic/rule-based intelligence layer.
    try:
        interpretation = palm_interpretation_engine.interpret(features)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Palm interpretation could not be generated.",
        )

    # Keep the raw CV features and attach the dedicated interpretation result.
    features["interpretation"] = interpretation

    reading = Reading(
        user_id=current_user.id,
        reading_type="PALMISTRY",
        overall_insight_score=None,
        analysis_data=features,
    )

    db.add(reading)

    try:
        await db.commit()
        await db.refresh(reading)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Palm analysis completed but the reading could not be saved.",
        )

    return {
        "status": "success",
        "reading_id": str(reading.id),
        "result": result,
    }
