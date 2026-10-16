from __future__ import annotations

import json
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings


class ReadingSynthesisEngine:
    """
    Combines Palmistry and Tarot results into a structured reading.

    M3.1 adds an AI interpretation layer using the configured OpenRouter model.

    The existing deterministic synthesis remains the fallback so the
    application continues to work when the external AI service is unavailable.

    No model training or fine-tuning is performed by this service.
    """

    # ============================================================
    # INSIGHT SCORE WEIGHTS
    # ============================================================

    PALM_WEIGHT = 0.30
    TAROT_WEIGHT = 0.25
    PERSONALITY_WEIGHT = 0.20
    CONTEXT_WEIGHT = 0.15
    CONSISTENCY_WEIGHT = 0.10

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self) -> None:
        self._openrouter_client: OpenAI | None = None

        api_key = getattr(
            settings,
            "OPENROUTER_API_KEY",
            None,
        )

        if api_key:
            api_key = api_key.strip()

            if api_key:
                try:
                    self._openrouter_client = OpenAI(
                        api_key=api_key,
                        base_url="https://openrouter.ai/api/v1",
                    )

                except Exception as exc:
                    print(
                        "OpenRouter client initialization error:",
                        type(exc).__name__,
                        str(exc),
                    )

                    self._openrouter_client = None

        self.model = getattr(
            settings,
            "OPENROUTER_MODEL",
            "openrouter/free",
        )

        if isinstance(self.model, str):
            self.model = self.model.strip()

        if not self.model:
            self.model = "openrouter/free"

    # ============================================================
    # COMMON HELPERS
    # ============================================================

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 100.0,
    ) -> float:
        return max(
            minimum,
            min(maximum, value),
        )

    @staticmethod
    def _round_score(
        value: float,
    ) -> float:
        return round(
            ReadingSynthesisEngine._clamp(
                float(value)
            ),
            2,
        )

    @staticmethod
    def _safe_dict(
        value: Any,
    ) -> Dict[str, Any]:
        return (
            value
            if isinstance(value, dict)
            else {}
        )

    @staticmethod
    def _safe_list(
        value: Any,
    ) -> List[Any]:
        return (
            value
            if isinstance(value, list)
            else []
        )

    @staticmethod
    def _get_palm_features(
        palm_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Support both wrapped and direct palm feature dictionaries.
        """

        if not isinstance(
            palm_data,
            dict,
        ):
            return {}

        features = palm_data.get(
            "features"
        )

        if isinstance(
            features,
            dict,
        ):
            return features

        return palm_data

    # ============================================================
    # PALM CONFIDENCE
    # ============================================================

    @staticmethod
    def _calculate_palm_confidence(
        palm_features: Dict[str, Any],
    ) -> float:
        """
        Calculate confidence from actual Palm-engine image evidence.
        """

        if not isinstance(
            palm_features,
            dict,
        ):
            return 0.0

        major_lines = palm_features.get(
            "major_lines",
            {},
        )

        if not isinstance(
            major_lines,
            dict,
        ):
            return 0.0

        line_scores: List[float] = []

        for line_data in major_lines.values():

            if not isinstance(
                line_data,
                dict,
            ):
                continue

            evidence = line_data.get(
                "image_evidence",
                {},
            )

            if not isinstance(
                evidence,
                dict,
            ):
                evidence = {}

            characteristics = line_data.get(
                "characteristics",
                {},
            )

            if not isinstance(
                characteristics,
                dict,
            ):
                characteristics = {}

            components: List[float] = []

            clarity = evidence.get(
                "clarity_score"
            )

            if isinstance(
                clarity,
                (int, float),
            ):

                components.append(
                    ReadingSynthesisEngine._clamp(
                        float(clarity),
                        0.0,
                        1.0,
                    )
                )

            support = evidence.get(
                "support_ratio"
            )

            if isinstance(
                support,
                (int, float),
            ):

                components.append(
                    ReadingSynthesisEngine._clamp(
                        float(support),
                        0.0,
                        1.0,
                    )
                )

            continuity = characteristics.get(
                "continuity_proxy"
            )

            if isinstance(
                continuity,
                (int, float),
            ):

                components.append(
                    ReadingSynthesisEngine._clamp(
                        float(continuity),
                        0.0,
                        1.0,
                    )
                )

            if components:

                line_scores.append(
                    sum(components)
                    / len(components)
                )

        if line_scores:

            return (
                ReadingSynthesisEngine
                ._round_score(
                    (
                        sum(line_scores)
                        / len(line_scores)
                    )
                    * 100.0
                )
            )

        detection = palm_features.get(
            "detection",
            {},
        )

        if isinstance(
            detection,
            dict,
        ):

            confidence = detection.get(
                "confidence"
            )

            if isinstance(
                confidence,
                (int, float),
            ):

                return (
                    ReadingSynthesisEngine
                    ._round_score(
                        float(confidence)
                        * 100.0
                    )
                )

        return 50.0

    # ============================================================
    # TAROT RELEVANCE
    # ============================================================

    @staticmethod
    def _calculate_tarot_relevance(
        tarot_data: Dict[str, Any],
    ) -> float:
        """
        Estimate Tarot interpretation relevance from supplied evidence.
        """

        if not isinstance(
            tarot_data,
            dict,
        ):
            return 0.0

        cards = tarot_data.get(
            "cards",
            [],
        )

        if (
            not isinstance(cards, list)
            or not cards
        ):
            return 0.0

        spread_type = str(
            tarot_data.get(
                "spread_type",
                "three_card",
            )
        ).strip().lower()

        spread_keywords = {
            "single": {
                "focus",
                "guidance",
                "theme",
                "energy",
                "present",
                "lesson",
                "choice",
                "direction",
            },
            "three_card": {
                "past",
                "present",
                "future",
                "journey",
                "change",
                "growth",
                "direction",
                "lesson",
            },
            "relationship": {
                "love",
                "relationship",
                "connection",
                "emotion",
                "partner",
                "partnership",
                "bond",
                "trust",
                "communication",
                "conflict",
                "harmony",
            },
            "career": {
                "career",
                "work",
                "goal",
                "success",
                "achievement",
                "ambition",
                "skill",
                "project",
                "leadership",
                "finance",
                "opportunity",
                "responsibility",
            },
            "life_path": {
                "journey",
                "path",
                "purpose",
                "growth",
                "change",
                "spiritual",
                "lesson",
                "direction",
                "opportunity",
                "choice",
                "transformation",
            },
            "celtic_cross": {
                "challenge",
                "influence",
                "foundation",
                "past",
                "future",
                "outcome",
                "direction",
                "hope",
                "fear",
                "environment",
                "opportunity",
            },
        }

        keywords = spread_keywords.get(
            spread_type,
            spread_keywords["three_card"],
        )

        evidence_scores: List[float] = []
        thematic_scores: List[float] = []

        valid_orientations = 0
        positions_present = 0

        for card in cards:

            if not isinstance(
                card,
                dict,
            ):
                continue

            name = str(
                card.get("card_name")
                or card.get("name")
                or ""
            ).strip()

            orientation = str(
                card.get("orientation")
                or ""
            ).strip().lower()

            interpretation = str(
                card.get("interpretation")
                or card.get("meaning")
                or card.get("meaning_upright")
                or card.get("meaning_reversed")
                or ""
            ).strip()

            position = str(
                card.get("position")
                or card.get("position_name")
                or ""
            ).strip()

            evidence = 0.0

            if name:
                evidence += 35.0

            if orientation in {
                "upright",
                "reversed",
            }:

                evidence += 20.0
                valid_orientations += 1

            if interpretation:
                evidence += 35.0

            if position:
                evidence += 10.0
                positions_present += 1

            evidence_scores.append(
                evidence
            )

            text = (
                f"{name} "
                f"{position} "
                f"{interpretation}"
            ).lower()

            matches = sum(
                1
                for keyword in keywords
                if keyword in text
            )

            thematic_scores.append(
                min(
                    100.0,
                    (
                        matches
                        / max(
                            1,
                            min(
                                5,
                                len(keywords),
                            ),
                        )
                    )
                    * 100.0,
                )
            )

        if not evidence_scores:
            return 0.0

        evidence_average = (
            sum(evidence_scores)
            / len(evidence_scores)
        )

        thematic_average = (
            sum(thematic_scores)
            / len(thematic_scores)
            if thematic_scores
            else 0.0
        )

        orientation_quality = (
            valid_orientations
            / len(evidence_scores)
        ) * 100.0

        position_quality = (
            positions_present
            / len(evidence_scores)
        ) * 100.0

        score = (
            evidence_average * 0.50
            + thematic_average * 0.30
            + orientation_quality * 0.10
            + position_quality * 0.10
        )

        return (
            ReadingSynthesisEngine
            ._round_score(score)
        )

    # ============================================================
    # PERSONALITY / USER CONTEXT
    # ============================================================

    @staticmethod
    def _calculate_personality_alignment(
        palm_features: Dict[str, Any],
        personality_data: Dict[str, Any] | None,
    ) -> float:

        if not personality_data:
            return 50.0

        alignment = personality_data.get(
            "alignment_score"
        )

        if isinstance(
            alignment,
            (int, float),
        ):

            return (
                ReadingSynthesisEngine
                ._round_score(
                    float(alignment)
                )
            )

        return 50.0

    @staticmethod
    def _calculate_context_relevance(
        user_context: Dict[str, Any] | None,
    ) -> float:

        if not user_context:
            return 50.0

        relevance = user_context.get(
            "relevance_score"
        )

        if isinstance(
            relevance,
            (int, float),
        ):

            return (
                ReadingSynthesisEngine
                ._round_score(
                    float(relevance)
                )
            )

        return 50.0

    # ============================================================
    # CONSISTENCY
    # ============================================================

    @staticmethod
    def _calculate_consistency(
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
    ) -> float:
        """
        Compare observable Palm themes with supplied Tarot text.
        """

        if (
            not isinstance(
                palm_features,
                dict,
            )
            or not isinstance(
                tarot_data,
                dict,
            )
        ):
            return 50.0

        cards = tarot_data.get(
            "cards",
            [],
        )

        if (
            not isinstance(cards, list)
            or not cards
        ):
            return 50.0

        hand_type = palm_features.get(
            "hand_type",
            {},
        )

        if not isinstance(
            hand_type,
            dict,
        ):
            hand_type = {}

        element = str(
            hand_type.get(
                "element",
                "",
            )
        ).lower()

        if not element:

            palm_structure = palm_features.get(
                "palm_structure",
                {},
            )

            if not isinstance(
                palm_structure,
                dict,
            ):
                palm_structure = {}

            if (
                palm_structure.get(
                    "is_finger_long"
                )
                is True
                and palm_structure.get(
                    "is_palm_square"
                )
                is False
            ):

                element = "water"

            elif (
                palm_structure.get(
                    "is_finger_long"
                )
                is False
                and palm_structure.get(
                    "is_palm_square"
                )
                is True
            ):

                element = "earth"

        element_keywords = {
            "water": {
                "emotion",
                "feeling",
                "intuition",
                "imagination",
                "compassion",
                "sensitive",
                "love",
                "connection",
            },
            "fire": {
                "action",
                "energy",
                "ambition",
                "courage",
                "leadership",
                "passion",
                "initiative",
                "confidence",
            },
            "earth": {
                "stability",
                "practical",
                "work",
                "finance",
                "security",
                "discipline",
                "material",
                "responsibility",
            },
            "air": {
                "thought",
                "intellect",
                "communication",
                "ideas",
                "clarity",
                "logic",
                "decision",
                "knowledge",
            },
        }

        palm_keywords = set(
            element_keywords.get(
                element,
                set(),
            )
        )

        major_lines = palm_features.get(
            "major_lines",
            {},
        )

        if isinstance(
            major_lines,
            dict,
        ):

            line_keywords = {
                "life_line": {
                    "vitality",
                    "energy",
                    "foundation",
                    "change",
                },
                "head_line": {
                    "thought",
                    "mind",
                    "logic",
                    "decision",
                    "ideas",
                },
                "heart_line": {
                    "love",
                    "emotion",
                    "relationship",
                    "connection",
                    "feeling",
                },
                "fate_line": {
                    "career",
                    "work",
                    "purpose",
                    "direction",
                    "goal",
                },
                "sun_line": {
                    "creativity",
                    "recognition",
                    "success",
                    "achievement",
                },
            }

            for line_name, line_data in (
                major_lines.items()
            ):

                if isinstance(
                    line_data,
                    dict,
                ):

                    palm_keywords.update(
                        line_keywords.get(
                            line_name,
                            set(),
                        )
                    )

        if not palm_keywords:
            return 50.0

        scores: List[float] = []

        for card in cards:

            if not isinstance(
                card,
                dict,
            ):
                continue

            text = " ".join(
                str(
                    card.get(
                        field,
                        "",
                    )
                )
                for field in (
                    "card_name",
                    "name",
                    "position",
                    "position_name",
                    "interpretation",
                    "meaning",
                    "meaning_upright",
                    "meaning_reversed",
                )
            ).lower()

            matches = sum(
                1
                for keyword in palm_keywords
                if keyword in text
            )

            if matches:

                card_score = (
                    45.0
                    + (
                        matches
                        * 15.0
                    )
                )

            else:

                card_score = 35.0

            orientation = str(
                card.get(
                    "orientation",
                    "",
                )
            ).lower()

            if orientation in {
                "upright",
                "reversed",
            }:

                card_score += 5.0

            scores.append(
                min(
                    100.0,
                    card_score,
                )
            )

        if not scores:
            return 50.0

        return (
            ReadingSynthesisEngine
            ._round_score(
                sum(scores)
                / len(scores)
            )
        )

    # ============================================================
    # HAND / SUMMARY BUILDERS
    # ============================================================

    @staticmethod
    def _resolve_hand_type(
        palm_features: Dict[str, Any],
    ) -> str:

        hand_type = palm_features.get(
            "hand_type",
            {},
        )

        if not isinstance(
            hand_type,
            dict,
        ):
            hand_type = {}

        explicit_type = (
            hand_type.get("type")
            or hand_type.get("name")
        )

        if explicit_type:
            return str(
                explicit_type
            )

        element = hand_type.get(
            "element"
        )

        if isinstance(
            element,
            str,
        ):

            normalized = (
                element
                .strip()
                .lower()
            )

            for known_element in (
                "water",
                "fire",
                "earth",
                "air",
            ):

                if normalized.startswith(
                    known_element
                ):

                    return (
                        f"{known_element.title()} Hand"
                    )

        palm_structure = palm_features.get(
            "palm_structure",
            {},
        )

        if not isinstance(
            palm_structure,
            dict,
        ):
            palm_structure = {}

        if (
            palm_structure.get(
                "is_finger_long"
            )
            is True
            and palm_structure.get(
                "is_palm_square"
            )
            is False
        ):

            return "Water Hand"

        if (
            palm_structure.get(
                "is_finger_long"
            )
            is False
            and palm_structure.get(
                "is_palm_square"
            )
            is True
        ):

            return "Earth Hand"

        return "Unknown"

    @staticmethod
    def _build_palm_summary(
        palm_features: Dict[str, Any],
    ) -> Dict[str, Any]:

        hand_type = palm_features.get(
            "hand_type",
            {},
        )

        if not isinstance(
            hand_type,
            dict,
        ):
            hand_type = {}

        palm_structure = palm_features.get(
            "palm_structure",
            {},
        )

        if not isinstance(
            palm_structure,
            dict,
        ):
            palm_structure = {}

        major_lines = palm_features.get(
            "major_lines",
            {},
        )

        if not isinstance(
            major_lines,
            dict,
        ):
            major_lines = {}

        return {
            "element": hand_type.get(
                "element",
                "Unknown",
            ),
            "hand_type": (
                ReadingSynthesisEngine
                ._resolve_hand_type(
                    palm_features
                )
            ),
            "major_lines": major_lines,
            "palm_structure": palm_structure,
        }

    @staticmethod
    def _build_card_highlights(
        cards: List[Dict[str, Any]],
    ) -> List[str]:

        highlights: List[str] = []

        for card in cards:

            if not isinstance(
                card,
                dict,
            ):
                continue

            name = (
                card.get("card_name")
                or card.get("name")
                or "Unknown Card"
            )

            orientation = (
                card.get(
                    "orientation"
                )
                or "Upright"
            )

            highlights.append(
                f"{name} ({orientation})"
            )

        return highlights

    @staticmethod
    def _build_tarot_summary(
        tarot_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        cards = tarot_data.get(
            "cards",
            [],
        )

        if not isinstance(
            cards,
            list,
        ):
            cards = []

        return {
            "spread_type": tarot_data.get(
                "spread_type",
                "three_card",
            ),
            "total_cards": len(cards),
            "cards": cards,
            "card_highlights": (
                ReadingSynthesisEngine
                ._build_card_highlights(
                    cards
                )
            ),
        }

    # ============================================================
    # RULE-BASED FALLBACK NARRATIVE
    # ============================================================

    @staticmethod
    def _generate_narrative(
        user_name: str,
        palm_summary: Dict[str, Any],
        tarot_summary: Dict[str, Any],
    ) -> str:

        name = (
            user_name
            or "User"
        )

        element = palm_summary.get(
            "element",
            "an undetermined",
        )

        hand_type = palm_summary.get(
            "hand_type",
            "unknown",
        )

        spread_type = tarot_summary.get(
            "spread_type",
            "three_card",
        )

        total_cards = tarot_summary.get(
            "total_cards",
            0,
        )

        cards = tarot_summary.get(
            "card_highlights",
            [],
        )

        opening = (
            f"{name}, the palm analysis indicates "
            f"a {hand_type} associated with "
            f"{element} characteristics. "
        )

        if total_cards == 0:

            tarot_part = (
                "No Tarot cards were available "
                "for cross-reference."
            )

        elif total_cards == 1:

            tarot_part = (
                "The Tarot reading contains a "
                f"single focus card: {cards[0]}."
            )

        else:

            card_text = ", ".join(
                cards[:3]
            )

            if total_cards > 3:
                card_text += (
                    ", and additional cards"
                )

            tarot_part = (
                f"The "
                f"{str(spread_type).replace('_', ' ').title()} "
                f"spread contains {total_cards} cards. "
                f"The primary Tarot signals are "
                f"{card_text}."
            )

        closing = (
            "Together, these results provide a "
            "reflective interpretation of the supplied "
            "palm and Tarot inputs. They should be treated "
            "as guidance rather than factual predictions."
        )

        return (
            opening
            + tarot_part
            + " "
            + closing
        )

    @staticmethod
    def _generate_actionable_advice(
        palm_summary: Dict[str, Any],
        tarot_summary: Dict[str, Any],
    ) -> List[str]:

        advice: List[str] = []

        element = palm_summary.get(
            "element",
            "your observed traits",
        )

        advice.append(
            f"Use the strengths associated with "
            f"{element} as a reflection point when "
            "making important decisions."
        )

        cards = tarot_summary.get(
            "cards",
            [],
        )

        if (
            isinstance(cards, list)
            and cards
        ):

            first_card = cards[0]

            if isinstance(
                first_card,
                dict,
            ):

                card_name = (
                    first_card.get(
                        "card_name"
                    )
                    or first_card.get(
                        "name"
                    )
                    or "your primary Tarot card"
                )

                advice.append(
                    "Reflect on the central theme "
                    f"represented by {card_name} "
                    "before making major commitments."
                )

        major_lines = palm_summary.get(
            "major_lines",
            {},
        )

        if isinstance(
            major_lines,
            dict,
        ):

            if "fate_line" in major_lines:

                advice.append(
                    "Consider setting measurable goals "
                    "and reviewing your progress periodically."
                )

            if "head_line" in major_lines:

                advice.append(
                    "Give yourself time to evaluate "
                    "important choices from multiple "
                    "perspectives."
                )

        advice.append(
            "Use the reading as a reflective tool "
            "rather than as a substitute for professional "
            "advice or evidence-based decision making."
        )

        return advice

    # ============================================================
    # M3.1 AI INTERPRETATION ENGINE
    # ============================================================

    def _build_ai_payload(
        self,
        user_name: str,
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
        personality_data: Dict[str, Any] | None,
        user_context: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """
        Build a bounded, structured payload for the LLM.

        Raw palm images are never sent here.
        The model receives only structured output produced
        by the Palm engine.
        """

        palm_summary = (
            self._build_palm_summary(
                palm_features
            )
        )

        tarot_summary = (
            self._build_tarot_summary(
                tarot_data
            )
        )

        return {
            "user_name": (
                user_name
                or "User"
            ),
            "palm_analysis": palm_summary,
            "tarot_reading": tarot_summary,
            "personality_data": (
                personality_data
                or {}
            ),
            "user_context": (
                user_context
                or {}
            ),
        }

    def _generate_ai_interpretation(
        self,
        user_name: str,
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
        personality_data: Dict[str, Any] | None,
        user_context: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        """
        Generate structured interpretation using the configured
        OpenRouter model.

        Returns None when AI is unavailable or returns invalid
        data, allowing the deterministic synthesis path to remain
        operational.
        """

        # --------------------------------------------------------
        # Verify OpenRouter client
        # --------------------------------------------------------

        if self._openrouter_client is None:

            print(
                "OpenRouter interpretation skipped: "
                "OpenRouter client is not initialized."
            )

            return None

        # --------------------------------------------------------
        # Build payload
        # --------------------------------------------------------

        payload = self._build_ai_payload(
            user_name=user_name,
            palm_features=palm_features,
            tarot_data=tarot_data,
            personality_data=personality_data,
            user_context=user_context,
        )

        # --------------------------------------------------------
        # System prompt
        # --------------------------------------------------------

        system_prompt = """
You are the AI interpretation layer of a Palmistry & Tarot
reflection application.

Use ONLY the structured evidence supplied in the user payload.

Do not invent:
- palm features
- Tarot cards
- Tarot positions
- Tarot meanings
- personality traits
- user facts

Palmistry and Tarot are reflective/spiritual systems, not
scientifically validated methods for predicting a person's future.

Therefore:

- Do not state predictions as facts.
- Do not make medical claims.
- Do not make financial claims.
- Do not make legal claims.
- Do not claim certainty about personality.
- Do not claim certainty about future events.
- Phrase interpretations as reflective possibilities.
- Keep the interpretation grounded in the supplied evidence.

Return ONLY valid JSON with exactly these keys:

{
  "interpretation": "string",
  "key_themes": ["string"],
  "personality_alignment": 0,
  "context_relevance": 0,
  "actionable_advice": ["string"]
}

Scoring guidance:

- personality_alignment: 0-100, based only on supplied
  personality data and observable alignment with the supplied
  Palm/Tarot themes.

- context_relevance: 0-100, based only on supplied user
  context and how directly the reading addresses it.

- If relevant information is absent, use 50 rather than
  inventing evidence.

- Keep both scores between 0 and 100.

- Provide 3 to 6 key themes.

- Provide 3 to 6 practical, reflective actions.
"""

        # --------------------------------------------------------
        # User prompt
        # --------------------------------------------------------

        user_prompt = (
            "Create a personalized reflective interpretation "
            "from this structured reading data:\n\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                default=str,
            )
        )

        # --------------------------------------------------------
        # OpenRouter request
        # --------------------------------------------------------

        try:

            print(
                "OpenRouter interpretation request started."
            )

            print(
                "OpenRouter model:",
                self.model,
            )

            response = (
                self._openrouter_client
                .chat.completions.create(
                    model=self.model,
                    temperature=0.4,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                system_prompt.strip()
                            ),
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                )
            )

            # ----------------------------------------------------
            # Extract response
            # ----------------------------------------------------

            if not response.choices:

                print(
                    "OpenRouter interpretation error: "
                    "No choices returned."
                )

                return None

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if not content:

                print(
                    "OpenRouter interpretation error: "
                    "Empty response content."
                )

                return None

            # ----------------------------------------------------
            # Reject provider safety/status placeholders
            # ----------------------------------------------------
            # Some OpenRouter routes/models return a plain-text status such
            # as "User Safety: safe" instead of the requested JSON object.
            # This is not a reading and cannot be repaired by JSON parsing.
            # Return None so generate_composite_report() uses its existing
            # deterministic fallback rather than exposing the placeholder.

            cleaned_content = content.strip()
            normalized_content = cleaned_content.casefold()
            if (
                normalized_content.startswith("user safety:")
                or normalized_content in {
                    "safe",
                    "unsafe",
                    "content filtered",
                    "response blocked",
                }
            ):
                print(
                    "OpenRouter returned a safety/status placeholder "
                    "instead of JSON; using deterministic fallback."
                )
                return None

            # ----------------------------------------------------
            # Parse JSON robustly
            # ----------------------------------------------------

            # Models sometimes wrap JSON in Markdown fences.
            if cleaned_content.startswith("```"):
                lines = cleaned_content.splitlines()
                if lines and lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_content = "\n".join(lines).strip()

            try:
                result = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # If the model adds explanatory text around the JSON,
                # isolate the outermost JSON object and try once more.
                start = cleaned_content.find("{")
                end = cleaned_content.rfind("}")

                if start >= 0 and end > start:
                    try:
                        result = json.loads(
                            cleaned_content[start : end + 1]
                        )
                    except json.JSONDecodeError as exc:
                        print(
                            "OpenRouter interpretation JSON error:",
                            type(exc).__name__,
                            str(exc),
                        )
                        print(
                            "OpenRouter response was not valid JSON; "
                            "response content omitted from logs."
                        )
                        return None
                else:
                    print(
                        "OpenRouter interpretation JSON error: "
                        "response did not contain a JSON object."
                    )
                    print(
                        "OpenRouter response did not contain a JSON object; "
                        "response content omitted from logs."
                    )
                    return None

            if not isinstance(
                result,
                dict,
            ):

                print(
                    "OpenRouter interpretation error: "
                    "Response JSON is not an object."
                )

                return None

            # ----------------------------------------------------
            # Extract fields
            # ----------------------------------------------------

            interpretation = result.get(
                "interpretation"
            )

            themes = result.get(
                "key_themes"
            )

            advice = result.get(
                "actionable_advice"
            )

            personality = result.get(
                "personality_alignment"
            )

            context = result.get(
                "context_relevance"
            )

            # ----------------------------------------------------
            # Validate interpretation
            # ----------------------------------------------------

            if (
                not isinstance(
                    interpretation,
                    str,
                )
                or not interpretation.strip()
            ):

                print(
                    "OpenRouter interpretation error: "
                    "Missing or invalid interpretation."
                )

                return None

            # ----------------------------------------------------
            # Validate themes
            # ----------------------------------------------------

            if not isinstance(
                themes,
                list,
            ):

                themes = []

            # ----------------------------------------------------
            # Validate advice
            # ----------------------------------------------------

            if not isinstance(
                advice,
                list,
            ):

                advice = []

            # ----------------------------------------------------
            # Validate personality score
            # ----------------------------------------------------

            if not isinstance(
                personality,
                (int, float),
            ):

                personality = 50.0

            # ----------------------------------------------------
            # Validate context score
            # ----------------------------------------------------

            if not isinstance(
                context,
                (int, float),
            ):

                context = 50.0

            # ----------------------------------------------------
            # Build validated AI result
            # ----------------------------------------------------

            ai_result = {
                "interpretation": (
                    interpretation.strip()
                ),
                "key_themes": [
                    str(item).strip()
                    for item in themes
                    if str(item).strip()
                ][:6],
                "personality_alignment": (
                    self._round_score(
                        float(personality)
                    )
                ),
                "context_relevance": (
                    self._round_score(
                        float(context)
                    )
                ),
                "actionable_advice": [
                    str(item).strip()
                    for item in advice
                    if str(item).strip()
                ][:6],
                "model": self.model,
            }

            print(
                "OpenRouter interpretation generated successfully."
            )

            return ai_result

        except Exception as exc:

            # ----------------------------------------------------
            # IMPORTANT:
            # Keep fallback behavior, but expose the real
            # OpenAI error in the backend terminal.
            # ----------------------------------------------------

            print(
                "OpenRouter interpretation error:",
                type(exc).__name__,
                str(exc),
            )

            return None

    # ============================================================
    # COMPOSITE REPORT
    # ============================================================

    def generate_composite_report(
        self,
        user_name: str,
        palm_data: Dict[str, Any],
        tarot_data: Dict[str, Any],
        personality_data: Dict[str, Any] | None = None,
        user_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Generate a composite Palm + Tarot report.

        M3.1 behavior:

        1. Calculate deterministic evidence scores.
        2. Attempt AI interpretation.
        3. Use AI personality/context scores when successfully supplied.
        4. Fall back to deterministic narrative/advice if AI is unavailable.
        """

        # --------------------------------------------------------
        # Palm features
        # --------------------------------------------------------

        palm_features = (
            self._get_palm_features(
                palm_data
            )
        )

        # --------------------------------------------------------
        # Validate Tarot data
        # --------------------------------------------------------

        if not isinstance(
            tarot_data,
            dict,
        ):

            tarot_data = {}

        # --------------------------------------------------------
        # Build summaries
        # --------------------------------------------------------

        palm_summary = (
            self._build_palm_summary(
                palm_features
            )
        )

        tarot_summary = (
            self._build_tarot_summary(
                tarot_data
            )
        )

        # --------------------------------------------------------
        # Deterministic evidence scores
        # --------------------------------------------------------

        palm_confidence = (
            self._calculate_palm_confidence(
                palm_features
            )
        )

        tarot_relevance = (
            self._calculate_tarot_relevance(
                tarot_data
            )
        )

        # --------------------------------------------------------
        # AI interpretation
        # --------------------------------------------------------

        ai_result = (
            self._generate_ai_interpretation(
                user_name=user_name,
                palm_features=palm_features,
                tarot_data=tarot_data,
                personality_data=personality_data,
                user_context=user_context,
            )
        )

        # --------------------------------------------------------
        # AI success
        # --------------------------------------------------------

        if ai_result:

            personality_alignment = (
                ai_result[
                    "personality_alignment"
                ]
            )

            context_relevance = (
                ai_result[
                    "context_relevance"
                ]
            )

            narrative = (
                ai_result[
                    "interpretation"
                ]
            )

            ai_advice = (
                ai_result.get(
                    "actionable_advice",
                    [],
                )
            )

            actionable_advice = (
                ai_advice
                if ai_advice
                else self._generate_actionable_advice(
                    palm_summary,
                    tarot_summary,
                )
            )

        # --------------------------------------------------------
        # Rule-based fallback
        # --------------------------------------------------------

        else:

            personality_alignment = (
                self._calculate_personality_alignment(
                    palm_features,
                    personality_data,
                )
            )

            context_relevance = (
                self._calculate_context_relevance(
                    user_context
                )
            )

            narrative = (
                self._generate_narrative(
                    user_name=user_name,
                    palm_summary=palm_summary,
                    tarot_summary=tarot_summary,
                )
            )

            actionable_advice = (
                self._generate_actionable_advice(
                    palm_summary=palm_summary,
                    tarot_summary=tarot_summary,
                )
            )

        # --------------------------------------------------------
        # Consistency
        # --------------------------------------------------------

        consistency = (
            self._calculate_consistency(
                palm_features,
                tarot_data,
            )
        )

        # --------------------------------------------------------
        # Final weighted insight score
        # --------------------------------------------------------

        final_score = (
            palm_confidence
            * self.PALM_WEIGHT
            + tarot_relevance
            * self.TAROT_WEIGHT
            + personality_alignment
            * self.PERSONALITY_WEIGHT
            + context_relevance
            * self.CONTEXT_WEIGHT
            + consistency
            * self.CONSISTENCY_WEIGHT
        )

        final_score = (
            self._round_score(
                final_score
            )
        )

        # --------------------------------------------------------
        # Final report
        # --------------------------------------------------------

        return {
            "status": "success",

            "title": (
                "Palmistry & Tarot Synthesis for "
                f"{user_name or 'User'}"
            ),

            "insight_score": final_score,

            "interpretation_engine": {
                "type": (
                    "openrouter"
                    if ai_result
                    else "rule_based_fallback"
                ),
                "model": (
                    ai_result.get(
                        "model"
                    )
                    if ai_result
                    else None
                ),
            },

            "score_breakdown": {
                "palm_analysis_confidence": (
                    palm_confidence
                ),
                "tarot_interpretation_relevance": (
                    tarot_relevance
                ),
                "personality_alignment": (
                    personality_alignment
                ),
                "user_context_relevance": (
                    context_relevance
                ),
                "reading_consistency": (
                    consistency
                ),
                "weights": {
                    "palm_analysis_confidence": (
                        self.PALM_WEIGHT
                    ),
                    "tarot_interpretation_relevance": (
                        self.TAROT_WEIGHT
                    ),
                    "personality_alignment": (
                        self.PERSONALITY_WEIGHT
                    ),
                    "user_context_relevance": (
                        self.CONTEXT_WEIGHT
                    ),
                    "reading_consistency": (
                        self.CONSISTENCY_WEIGHT
                    ),
                },
            },

            "palm_summary": palm_summary,

            "tarot_spread_summary": (
                tarot_summary
            ),

            "synthesized_reading": narrative,

            "actionable_advice": (
                actionable_advice
            ),

            "ai_interpretation": (
                ai_result
            ),
        }


# ============================================================
# GLOBAL SYNTHESIS ENGINE INSTANCE
# ============================================================

synthesis_engine = (
    ReadingSynthesisEngine()
)