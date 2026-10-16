from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.relational import User, Reading
from app.services.tarot_service import tarot_engine


router = APIRouter()


@router.post("/draw")
async def draw_tarot(
    spread_type: str = Query(
        default="three_card",
        description=(
            "Tarot spread type: single, three_card, relationship, "
            "career, celtic_cross, or life_path."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Draw a Tarot spread for the authenticated user and store the reading.

    Supported spreads:
    - single
    - three_card
    - relationship
    - career
    - celtic_cross
    - life_path
    """

    spread_type = spread_type.strip().lower()

    try:
        # Generate the Tarot spread using the Tarot engine.
        cards_data = tarot_engine.draw_spread(
            spread_type=spread_type
        )

    except ValueError as exc:
        # Invalid spread / invalid Tarot configuration.
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        # Do not expose internal implementation errors to the client.
        raise HTTPException(
            status_code=500,
            detail="Tarot reading generation failed. Please try again.",
        )

    # Store the actual Tarot result.
    # The insight score will be calculated later by the
    # intelligence/synthesis layer rather than being hardcoded here.
    reading = Reading(
        user_id=current_user.id,
        reading_type="TAROT",
        overall_insight_score=None,
        analysis_data=cards_data,
    )

    db.add(reading)

    try:
        await db.commit()
        await db.refresh(reading)

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Tarot reading was generated but could not be saved.",
        )

    return {
        "status": "success",
        "reading_id": str(reading.id),
        "tarot": cards_data,
    }