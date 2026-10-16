import json

from typing import Any, Dict, Optional

from uuid import UUID



from fastapi import (

    APIRouter,

    Depends,

    File,

    Form,

    HTTPException,

    UploadFile,

)

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_current_user

from app.core.database import get_db

from app.models.relational import (

    User,

    Profile,

    Reading,

    Report,

)

from app.services.palm_service import palm_engine

from app.services.tarot_service import tarot_engine

from app.services.synthesis_service import synthesis_engine

from app.services.personality_service import personality_engine

from app.services.recommendation_service import recommendation_engine

from app.services.life_trends_service import life_trends_engine





router = APIRouter()


@router.get("/history")
async def get_reading_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's saved readings, newest first."""

    result = await db.execute(
        select(Reading)
        .where(Reading.user_id == current_user.id)
        .order_by(Reading.created_at.desc())
    )

    readings = result.scalars().all()

    return {
        "status": "success",
        "count": len(readings),
        "readings": [
            {
                "reading_id": str(reading.id),
                "reading_type": reading.reading_type,
                "created_at": (
                    reading.created_at.isoformat()
                    if reading.created_at
                    else None
                ),
                "insight_score": reading.overall_insight_score,
            }
            for reading in readings
        ],
    }






# ============================================================

# DASHBOARD STATS

# ============================================================



@router.get("/dashboard-stats")

async def get_dashboard_stats(

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    """

    Return dashboard statistics for the authenticated user.

    """



    # --------------------------------------------------------

    # Palm readings count

    # --------------------------------------------------------



    palm_result = await db.execute(

        select(Reading).where(

            Reading.user_id == current_user.id,

            Reading.reading_type == "PALMISTRY",

        )

    )



    palm_readings = palm_result.scalars().all()

    palm_count = len(palm_readings)



    # --------------------------------------------------------

    # Tarot readings count

    # --------------------------------------------------------



    tarot_result = await db.execute(

        select(Reading).where(

            Reading.user_id == current_user.id,

            Reading.reading_type == "TAROT",

        )

    )



    tarot_readings = tarot_result.scalars().all()



    # --------------------------------------------------------

    # Synthesized readings count

    # --------------------------------------------------------



    synthesized_result = await db.execute(

        select(Reading).where(

            Reading.user_id == current_user.id,

            Reading.reading_type == "SYNTHESIZED",

        )

    )



    synthesized_readings = (

        synthesized_result.scalars().all()

    )



    # Keep synthesized readings included in the

    # dashboard's tarot/combined reading count.

    tarot_count = (

        len(tarot_readings)

        + len(synthesized_readings)

    )



    # --------------------------------------------------------

    # Latest palm confidence

    # --------------------------------------------------------



    latest_confidence = None



    if palm_readings:



        latest_palm = max(

            palm_readings,

            key=lambda reading: (

                reading.created_at

                if reading.created_at

                else 0

            ),

        )



        analysis_data = (

            latest_palm.analysis_data

            or {}

        )



        # First try stored confidence.

        latest_confidence = (

            analysis_data.get(

                "analysis_confidence"

            )

        )



        # If not available, calculate it again

        # using the current synthesis engine.

        if latest_confidence is None:



            palm_features = (

                analysis_data.get(

                    "features",

                    analysis_data,

                )

            )



            try:



                latest_confidence = (

                    synthesis_engine

                    ._calculate_palm_confidence(

                        palm_features

                    )

                )



            except Exception:



                latest_confidence = None



    # --------------------------------------------------------

    # Total readings

    # --------------------------------------------------------



    total_readings = (

        palm_count

        + tarot_count

    )



    return {

        "status": "success",

        "stats": {

            "palm_readings": palm_count,

            "tarot_readings": tarot_count,

            "total_readings": total_readings,

            "latest_confidence": latest_confidence,

        },

    }





# ============================================================

# COMPOSITE PALM + TAROT READING

# ============================================================



@router.post("/composite-reading")

async def generate_composite_reading(

    spread_type: str = Form(

        default="three_card"

    ),

    palm_reading_id: Optional[str] = Form(

        default=None

    ),

    selected_card_ids: Optional[str] = Form(

        default=None,

        description=(

            "JSON array of Tarot catalog card IDs selected by the user. "

            "The selected cards are revealed only after submission."

        ),

    ),

    file: Optional[UploadFile] = File(

        default=None

    ),

    current_user: User = Depends(

        get_current_user

    ),

    db: AsyncSession = Depends(

        get_db

    ),

):

    """

    Generate a composite Palmistry + Tarot reading.



    Palm source priority:



    1. Explicit palm_reading_id

    2. Newly uploaded palm image

    3. Latest stored palm reading



    The selected palm data is combined with:

    - User-selected Tarot spread/cards

    - User profile

    - Dynamic persona

    - User context

    - M3.2 personality intelligence engine

    - M3.3 recommendation intelligence engine

    - M3.1 synthesis engine

    """



    # ========================================================

    # STEP 0 — NORMALIZE SPREAD TYPE

    # ========================================================



    spread_type = (

        spread_type

        .strip()

        .lower()

    )



    # ========================================================

    # STEP 1 — OBTAIN PALM DATA

    # ========================================================



    palm_features: Optional[

        Dict[str, Any]

    ] = None



    palm_source: Optional[str] = None



    # ========================================================

    # OPTION A — EXISTING PALM READING

    # ========================================================



    if palm_reading_id:



        try:



            palm_uuid = UUID(

                palm_reading_id

            )



        except ValueError:



            raise HTTPException(

                status_code=400,

                detail=(

                    "Invalid palm_reading_id. "

                    "Expected a valid UUID."

                ),

            )



        palm_result = await db.execute(

            select(Reading).where(

                Reading.id == palm_uuid,

                Reading.user_id == current_user.id,

                Reading.reading_type == "PALMISTRY",

            )

        )



        palm_reading = (

            palm_result

            .scalar_one_or_none()

        )



        if not palm_reading:



            raise HTTPException(

                status_code=404,

                detail=(

                    "Palm reading not found "

                    "for the authenticated user."

                ),

            )



        palm_analysis_data = (

            palm_reading.analysis_data

            or {}

        )



        palm_features = (

            palm_analysis_data.get(

                "features",

                palm_analysis_data,

            )

        )



        palm_source = (

            "existing_reading"

        )



    # ========================================================

    # OPTION B — NEW PALM IMAGE

    # ========================================================



    elif file is not None:



        # ----------------------------------------------------

        # Validate uploaded file

        # ----------------------------------------------------



        if (

            not file.content_type

            or not file.content_type.startswith(

                "image/"

            )

        ):



            raise HTTPException(

                status_code=400,

                detail=(

                    "Uploaded palm file "

                    "must be an image."

                ),

            )



        content = await file.read()



        if not content:



            raise HTTPException(

                status_code=400,

                detail=(

                    "Uploaded palm image "

                    "is empty."

                ),

            )



        # ----------------------------------------------------

        # Palm analysis

        # ----------------------------------------------------



        try:



            palm_result = (

                palm_engine

                .process_image(content)

            )



        except Exception as exc:



            print(

                "Palm analysis error:",

                repr(exc),

            )



            raise HTTPException(

                status_code=500,

                detail=(

                    "Palm image analysis failed. "

                    "Please try again."

                ),

            )



        # ----------------------------------------------------

        # Verify palm detection

        # ----------------------------------------------------



        if not palm_result.get(

            "detected"

        ):



            raise HTTPException(

                status_code=422,

                detail=(

                    palm_result.get(

                        "message",

                        (

                            "Could not detect a palm. "

                            "Please upload a clear "

                            "palm image."

                        ),

                    )

                ),

            )



        palm_features = (

            palm_result.get(

                "features"

            )

        )



        if not palm_features:



            raise HTTPException(

                status_code=422,

                detail=(

                    "Palm features could not "

                    "be extracted from the image."

                ),

            )



        palm_source = "new_image"



        # ----------------------------------------------------

        # Store new palm reading

        # ----------------------------------------------------



        new_palm_reading = Reading(

            user_id=current_user.id,

            reading_type="PALMISTRY",

            overall_insight_score=None,

            analysis_data=palm_features,

        )



        db.add(

            new_palm_reading

        )



        try:



            await db.commit()



            await db.refresh(

                new_palm_reading

            )



        except Exception as exc:



            await db.rollback()



            print(

                "Palm database error:",

                repr(exc),

            )



            raise HTTPException(

                status_code=500,

                detail=(

                    "Palm analysis completed "

                    "but could not be saved."

                ),

            )



    # ========================================================

    # OPTION C — LATEST STORED PALM READING

    # ========================================================



    else:



        latest_palm_result = (

            await db.execute(

                select(Reading)

                .where(

                    Reading.user_id

                    == current_user.id,

                    Reading.reading_type

                    == "PALMISTRY",

                )

                .order_by(

                    Reading.created_at.desc()

                )

                .limit(1)

            )

        )



        latest_palm = (

            latest_palm_result

            .scalar_one_or_none()

        )



        if not latest_palm:



            raise HTTPException(

                status_code=404,

                detail=(

                    "No palm reading is available. "

                    "Upload a palm image first."

                ),

            )



        palm_analysis_data = (

            latest_palm.analysis_data

            or {}

        )



        palm_features = (

            palm_analysis_data.get(

                "features",

                palm_analysis_data,

            )

        )



        palm_source = (

            "latest_reading"

        )



    # ========================================================

    # STEP 2 — VALIDATE PALM FEATURES

    # ========================================================



    if not palm_features:



        raise HTTPException(

            status_code=422,

            detail=(

                "Palm features are unavailable "

                "for composite synthesis."

            ),

        )



    # ========================================================

    # STEP 3 — GENERATE TAROT READING

    # ========================================================

    #

    # The new frontend supplies the exact cards selected by the

    # user from the shuffled 78-card deck. tarot_service validates

    # the card IDs and preserves the user's selection.

    #

    # No ML training or fine-tuning is involved.

    # ========================================================



    try:

        # --------------------------------------------------------

        # New Tarot interaction:

        #

        # 1. Frontend displays all 78 cards face-down.

        # 2. User shuffles the deck.

        # 3. User manually selects the required cards.

        # 4. Frontend sends their catalog IDs here.

        # 5. Backend reveals/processes exactly those cards.

        #

        # The backend must never replace user-selected cards with

        # a different random draw.

        # --------------------------------------------------------



        if selected_card_ids is not None:

            print("RAW selected_card_ids:", repr(selected_card_ids))
            try:

                parsed_selected_card_ids = json.loads(

                    selected_card_ids

                )

            except json.JSONDecodeError as exc:

                raise HTTPException(

                    status_code=400,

                    detail=(

                        "selected_card_ids must be a valid "

                        "JSON array of Tarot card IDs."

                    ),

                ) from exc



            if not isinstance(

                parsed_selected_card_ids,

                list,

            ):

                raise HTTPException(

                    status_code=400,

                    detail=(

                        "selected_card_ids must be a JSON array."

                    ),

                )



            tarot_result = tarot_engine.draw_selected_cards(

                spread_type=spread_type,

                selected_card_ids=parsed_selected_card_ids,

            )



        else:

            # Backward compatibility for older clients.

            # The new tarot.html always sends selected_card_ids.

            tarot_result = tarot_engine.draw_spread(

                spread_type=spread_type

            )



    except HTTPException:

        raise



    except ValueError as exc:



        raise HTTPException(

            status_code=400,

            detail=str(exc),

        )



    except Exception as exc:



        print(

            "Tarot generation error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Tarot reading generation "

                "failed. Please try again."

            ),

        )



    # ========================================================

    # STEP 4 — GET USER PROFILE

    # ========================================================



    profile_result = await db.execute(

        select(Profile).where(

            Profile.user_id

            == current_user.id

        )

    )



    profile = (

        profile_result

        .scalar_one_or_none()

    )



    # ========================================================

    # STEP 5 — USER CONTEXT

    # ========================================================



    user_context: Dict[str, Any] = {

        "age_group": None,

        "interests": None,

        "spiritual_goals": None,

    }



    if profile:



        user_context = {

            "age_group": (

                profile.age_group

            ),

            "interests": (

                profile.interests

            ),

            "spiritual_goals": (

                profile.spiritual_goals

            ),

        }



    # ========================================================

    # STEP 6 — USER NAME

    # ========================================================



    user_name: Optional[str] = None



    if profile and profile.full_name:



        user_name = (

            profile.full_name

        )



    if not user_name:



        email = getattr(

            current_user,

            "email",

            None,

        )



        if email:



            user_name = (

                email

                .split("@")[0]

                .replace(".", " ")

                .replace("_", " ")

                .title()

            )



        else:



            user_name = "User"



    # ========================================================

    # STEP 7 — PERSONALITY INTELLIGENCE (M3.2)

    # ========================================================



    # M3.2 is deterministic and rule-based. It uses the extracted

    # palm evidence, the current Tarot spread, and stored profile

    # context. No ML training or fine-tuning is performed here.

    try:

        personality_data = personality_engine.analyze(

            palm_features=palm_features,

            tarot_data=tarot_result,

            user_context=user_context,

        )



        # Preserve an existing profile persona as optional context

        # without replacing the M3.2 engine output.

        if profile and profile.dynamic_persona:

            personality_data["existing_dynamic_persona"] = (

                profile.dynamic_persona

            )



    except Exception as exc:

        print(

            "Personality intelligence error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Personality intelligence analysis failed. "

                "Please try again."

            ),

        )



    # ========================================================

    # STEP 8 — RECOMMENDATION INTELLIGENCE (M3.3)

    # ========================================================



    # M3.3 is deterministic and rule-based. It uses the same evidence

    # already produced by M2/M3.2 plus the supplied user context.

    # No ML training or fine-tuning is performed here.

    try:

        recommendation_data = recommendation_engine.generate(

            palm_features=palm_features,

            tarot_data=tarot_result,

            personality_data=personality_data,

            user_context=user_context,

        )

    except Exception as exc:

        print(

            "Recommendation intelligence error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Recommendation intelligence generation failed. "

                "Please try again."

            ),

        )



    # ========================================================

    # STEP 8 — LIFE TRENDS INTELLIGENCE (M3.4)

    # ========================================================



    # M3.4 is deterministic and rule-based. It identifies reflective

    # life-trend themes and opportunity areas from the evidence already

    # produced by M2, M3.2, and M3.3. It does not perform ML training

    # or future-event prediction.

    try:

        life_trends_data = life_trends_engine.analyze(

            palm_features=palm_features,

            tarot_data=tarot_result,

            personality_data=personality_data,

            recommendation_data=recommendation_data,

            user_context=user_context,

        )

    except Exception as exc:

        print(

            "Life trends intelligence error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Life trends intelligence analysis failed. "

                "Please try again."

            ),

        )



    # ========================================================

    # STEP 15 — PREPARE PALM DATA

    # ========================================================





    palm_data = {

        "detected": True,

        "features": palm_features,

    }



    # ========================================================

    # STEP 9 — GENERATE COMPOSITE SYNTHESIS

    # ========================================================



    try:



        report_data = (

            synthesis_engine

            .generate_composite_report(

                user_name=user_name,

                palm_data=palm_data,

                tarot_data=tarot_result,

                personality_data=(

                    personality_data

                ),

                user_context=user_context,

            )

        )



    except Exception as exc:



        print(

            "Composite synthesis error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Composite reading synthesis "

                "failed. Please try again."

            ),

        )



    # ========================================================

    # STEP 10 — ATTACH M3 INTELLIGENCE TO REPORT

    # ========================================================



    # The frontend stores only data.report in sessionStorage.

    # Therefore the complete report object must contain the

    # M3.2, M3.3, and M3.4 outputs as well as the M3.1 synthesis.

    #

    # This keeps the backend response and report.html data contract

    # consistent without requiring the frontend to reconstruct

    # intelligence data from top-level API fields.



    if not isinstance(report_data, dict):

        raise HTTPException(

            status_code=500,

            detail=(

                "Composite synthesis returned an invalid "

                "report structure."

            ),

        )



    report_data = {

        **report_data,

        "personality_intelligence": personality_data,

        "recommendation_intelligence": recommendation_data,

        "life_trends_intelligence": life_trends_data,

    }



    # Keep all intelligence outputs together as an optional

    # grouped object for future frontend/API consumers.

    report_data["intelligence"] = {

        "personality": personality_data,

        "recommendations": recommendation_data,

        "life_trends": life_trends_data,

    }



    # ========================================================

    # STEP 11 — EXTRACT INSIGHT SCORE

    # ========================================================



    insight_score = (

        report_data.get(

            "insight_score"

        )

    )



    if not isinstance(

        insight_score,

        (int, float),

    ):



        insight_score = (

            report_data.get(

                "overall_insight_score"

            )

        )



    if not isinstance(

        insight_score,

        (int, float),

    ):



        insight_score = None



    # ========================================================

    # STEP 12 — CREATE SYNTHESIZED READING

    # ========================================================



    reading = Reading(

        user_id=current_user.id,

        reading_type="SYNTHESIZED",

        overall_insight_score=(

            insight_score

        ),

        analysis_data={

            "palm_features": palm_features,

            "tarot": tarot_result,

            "tarot_selection_mode": tarot_result.get(

                "selection_mode",

                "random",

            ),

            "selected_tarot_card_ids": tarot_result.get(

                "selected_card_ids",

                [],

            ),

            "synthesis": report_data,

            "user_context": user_context,

            "personality_data": (

                personality_data

            ),

            "recommendations": recommendation_data,

            "life_trends": life_trends_data,

        },

    )



    db.add(reading)



    # --------------------------------------------------------

    # Flush first so reading.id is generated

    # before creating the Report.

    # --------------------------------------------------------



    try:



        await db.flush()



    except Exception as exc:



        await db.rollback()



        print(

            "Synthesized reading database error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Synthesized reading "

                "could not be created."

            ),

        )



    # ========================================================

    # STEP 13 — CREATE REPORT

    # ========================================================



    report_entry = Report(

        user_id=current_user.id,

        reading_id=reading.id,

        report_title=(

            f"Palmistry & Tarot Synthesis: "

            f"{user_name}"

        ),

        report_summary=(

            report_data.get(

                "synthesized_reading"

            )

        ),

        actionable_steps=(

            report_data.get(

                "actionable_advice",

                [],

            )

        ),

    )



    db.add(

        report_entry

    )



    # ========================================================

    # STEP 14 — COMMIT EVERYTHING

    # ========================================================



    try:



        await db.commit()



        await db.refresh(

            reading

        )



        await db.refresh(

            report_entry

        )



    except Exception as exc:



        await db.rollback()



        print(

            "Composite database error:",

            repr(exc),

        )



        raise HTTPException(

            status_code=500,

            detail=(

                "Composite reading "

                "could not be saved."

            ),

        )



    # ========================================================

    # STEP 15 — RESPONSE

    # ========================================================



    return {

        "status": "success",

        "reading_id": str(

            reading.id

        ),

        "report_id": str(

            report_entry.id

        ),

        "palm_source": palm_source,

        "spread_type": spread_type,

        "tarot_selection_mode": tarot_result.get(

            "selection_mode",

            "random",

        ),

        "selected_tarot_card_ids": tarot_result.get(

            "selected_card_ids",

            [],

        ),

        "overall_insight_score": (

            insight_score

        ),

        "personality_intelligence": personality_data,

        "recommendation_intelligence": recommendation_data,

        "life_trends_intelligence": life_trends_data,

        "report": report_data,

    }