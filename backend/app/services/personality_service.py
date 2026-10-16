from __future__ import annotations

from typing import Any, Dict, List


class PersonalityIntelligenceEngine:
    """
    M3.2 Personality Intelligence layer.

    This module converts existing Palmistry, Tarot, and user-profile signals
    into a structured reflective personality profile.

    Important:
    - No ML training or fine-tuning is performed.
    - Palmistry/Tarot signals are treated as symbolic inputs, not scientific
      measurements of personality.
    - Missing evidence is represented conservatively rather than fabricated.
    """

    # ============================================================
    # PUBLIC API
    # ============================================================

    def analyze(
        self,
        palm_features: Dict[str, Any] | None = None,
        tarot_data: Dict[str, Any] | None = None,
        user_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        palm_features = self._safe_dict(palm_features)
        tarot_data = self._safe_dict(tarot_data)
        user_context = self._safe_dict(user_context)

        signals = self._extract_signals(
            palm_features=palm_features,
            tarot_data=tarot_data,
            user_context=user_context,
        )

        profile = self._build_profile(signals)
        strengths = self._build_strengths(signals)
        development_areas = self._build_development_areas(signals)
        behavioral_insights = self._build_behavioral_insights(signals)
        recommendations = self._build_recommendations(
            signals=signals,
            strengths=strengths,
            development_areas=development_areas,
        )

        alignment_score = self._calculate_alignment_score(
            signals=signals,
            profile=profile,
            user_context=user_context,
        )

        confidence = self._calculate_confidence(signals)

        return {
            "status": "success",
            "engine": "rule_based_personality_intelligence",
            "version": "M3.2",
            "disclaimer": (
                "This personality profile is a reflective interpretation "
                "based on symbolic palm/Tarot signals and supplied profile "
                "context. It is not a scientifically validated personality "
                "assessment or psychological diagnosis."
            ),
            "personality_profile": profile,
            "strengths": strengths,
            "development_areas": development_areas,
            "behavioral_insights": behavioral_insights,
            "personal_development_recommendations": recommendations,
            "alignment_score": alignment_score,
            "analysis_confidence": confidence,
            "evidence": {
                "palm_signals": signals["palm_signals"],
                "tarot_signals": signals["tarot_signals"],
                "profile_signals": signals["profile_signals"],
            },
        }

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _safe_list(value: Any) -> List[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
        return max(minimum, min(maximum, float(value)))

    @classmethod
    def _round_score(cls, value: float) -> float:
        return round(cls._clamp(value), 2)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _contains_any(text: str, keywords: set[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    # ============================================================
    # SIGNAL EXTRACTION
    # ============================================================

    def _extract_signals(
        self,
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        hand_type = self._safe_dict(palm_features.get("hand_type"))
        palm_structure = self._safe_dict(palm_features.get("palm_structure"))
        major_lines = self._safe_dict(palm_features.get("major_lines"))
        mounts = self._safe_dict(palm_features.get("mounts"))

        element = self._normalize_text(hand_type.get("element"))

        if not element:
            if (
                palm_structure.get("is_finger_long") is True
                and palm_structure.get("is_palm_square") is False
            ):
                element = "water"
            elif (
                palm_structure.get("is_finger_long") is False
                and palm_structure.get("is_palm_square") is True
            ):
                element = "earth"

        line_text = []
        line_signals: Dict[str, Any] = {}

        line_themes = {
            "life_line": {
                "vitality",
                "energy",
                "resilience",
                "experience",
                "change",
            },
            "head_line": {
                "thinking",
                "reasoning",
                "logic",
                "ideas",
                "decision",
                "mind",
            },
            "heart_line": {
                "emotion",
                "relationship",
                "connection",
                "love",
                "feeling",
                "empathy",
            },
            "fate_line": {
                "career",
                "purpose",
                "direction",
                "responsibility",
                "goal",
                "work",
            },
            "sun_line": {
                "creativity",
                "recognition",
                "self-expression",
                "achievement",
                "visibility",
            },
        }

        for line_name, line_data in major_lines.items():
            if not isinstance(line_data, dict):
                continue

            characteristics = self._safe_dict(line_data.get("characteristics"))
            evidence = self._safe_dict(line_data.get("image_evidence"))

            text = " ".join(
                [
                    str(line_data.get("insight", "")),
                    str(line_data.get("characteristic_interpretation", "")),
                    str(line_data.get("status", "")),
                ]
            ).lower()

            line_text.append(text)

            line_signals[line_name] = {
                "direction": characteristics.get("direction"),
                "curvature_level": characteristics.get("curvature_level"),
                "continuity_proxy": characteristics.get("continuity_proxy"),
                "clarity_score": evidence.get("clarity_score"),
                "support_ratio": evidence.get("support_ratio"),
                "themes": sorted(
                    keyword
                    for keyword in line_themes.get(line_name, set())
                    if keyword in text
                ),
            }

        mount_text = []
        for mount_name, mount_data in mounts.items():
            if isinstance(mount_data, dict):
                mount_text.append(
                    " ".join(
                        [
                            str(mount_name),
                            str(mount_data.get("name", "")),
                            str(mount_data.get("significance", "")),
                            str(mount_data.get("interpretation", "")),
                        ]
                    ).lower()
                )

        cards = self._safe_list(tarot_data.get("cards"))
        tarot_text_parts = []
        tarot_cards = []

        for card in cards:
            if not isinstance(card, dict):
                continue

            card_name = str(
                card.get("card_name")
                or card.get("name")
                or "Unknown Card"
            ).strip()

            orientation = str(
                card.get("orientation")
                or "Upright"
            ).strip()

            interpretation = str(
                card.get("interpretation")
                or card.get("meaning")
                or card.get("meaning_upright")
                or card.get("meaning_reversed")
                or ""
            ).strip()

            tarot_cards.append(
                {
                    "name": card_name,
                    "orientation": orientation,
                    "interpretation": interpretation,
                    "position": card.get("position"),
                }
            )

            tarot_text_parts.append(
                f"{card_name} {orientation} {interpretation}".lower()
            )

        interests = self._to_text_list(
            user_context.get("interests")
        )
        spiritual_goals = self._to_text_list(
            user_context.get("spiritual_goals")
        )

        profile_text = " ".join(interests + spiritual_goals).lower()

        return {
            "element": element,
            "hand_type": hand_type.get("type") or hand_type.get("name"),
            "is_finger_long": palm_structure.get("is_finger_long"),
            "is_palm_square": palm_structure.get("is_palm_square"),
            "line_signals": line_signals,
            "line_text": line_text,
            "mount_text": mount_text,
            "tarot_cards": tarot_cards,
            "tarot_text": tarot_text_parts,
            "profile_text": profile_text,
            "palm_signals": {
                "element": element,
                "hand_type": hand_type.get("type") or hand_type.get("name"),
                "major_line_count": len(line_signals),
                "mount_count": len(mount_text),
            },
            "tarot_signals": {
                "spread_type": tarot_data.get("spread_type"),
                "card_count": len(tarot_cards),
                "cards": tarot_cards,
            },
            "profile_signals": {
                "interests": interests,
                "spiritual_goals": spiritual_goals,
            },
        }

    @staticmethod
    def _to_text_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]

        return []

    # ============================================================
    # PERSONALITY PROFILE
    # ============================================================

    def _build_profile(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        element = signals["element"]
        palm_text = " ".join(signals["line_text"])
        tarot_text = " ".join(signals["tarot_text"])
        combined = f"{palm_text} {tarot_text} {signals['profile_text']}"

        traits: List[str] = []
        dimensions: Dict[str, str] = {}

        if element.startswith("water"):
            traits.extend(
                [
                    "empathy",
                    "imagination",
                    "emotional awareness",
                    "intuition",
                ]
            )
            dimensions["emotional_style"] = "emotionally attentive"
        elif element.startswith("fire"):
            traits.extend(
                [
                    "initiative",
                    "energy",
                    "ambition",
                    "self-expression",
                ]
            )
            dimensions["action_style"] = "action-oriented"
        elif element.startswith("earth"):
            traits.extend(
                [
                    "practicality",
                    "stability",
                    "discipline",
                    "responsibility",
                ]
            )
            dimensions["action_style"] = "structured and practical"
        elif element.startswith("air"):
            traits.extend(
                [
                    "curiosity",
                    "reasoning",
                    "communication",
                    "idea generation",
                ]
            )
            dimensions["thinking_style"] = "analytical and communicative"

        if self._contains_any(
            combined,
            {"thinking", "reasoning", "logic", "ideas", "decision"},
        ):
            dimensions["thinking_style"] = "reflective and reasoning-focused"

        if self._contains_any(
            combined,
            {"emotion", "relationship", "connection", "empathy", "love"},
        ):
            dimensions["social_style"] = "connection-oriented"

        if self._contains_any(
            combined,
            {"career", "purpose", "goal", "work", "responsibility"},
        ):
            dimensions["goal_orientation"] = "purpose and progress oriented"

        if self._contains_any(
            combined,
            {"creativity", "self-expression", "recognition", "achievement"},
        ):
            dimensions["expression_style"] = "creative and expressive"

        traits = self._unique(traits)

        return {
            "summary": self._profile_summary(
                element=element,
                traits=traits,
                dimensions=dimensions,
            ),
            "core_traits": traits[:8],
            "behavioral_dimensions": dimensions,
            "interpretation_basis": [
                "symbolic palm signals",
                "supplied Tarot themes",
                "supplied user context",
            ],
        }

    @staticmethod
    def _profile_summary(
        element: str,
        traits: List[str],
        dimensions: Dict[str, str],
    ) -> str:
        element_name = element.title() if element else "mixed"

        if traits:
            trait_text = ", ".join(traits[:4])
            return (
                f"The supplied reading suggests a {element_name}-associated "
                f"reflective profile with themes of {trait_text}. "
                "These themes describe possible tendencies for self-reflection, "
                "not fixed personality facts."
            )

        return (
            "The supplied reading does not contain enough structured signals "
            "for a specific personality profile, so a broad reflective profile "
            "is retained."
        )

    # ============================================================
    # STRENGTHS
    # ============================================================

    def _build_strengths(self, signals: Dict[str, Any]) -> List[Dict[str, Any]]:
        combined = (
            " ".join(signals["line_text"])
            + " "
            + " ".join(signals["tarot_text"])
        ).lower()

        strengths: List[Dict[str, Any]] = []

        strength_rules = [
            (
                {"emotion", "empathy", "connection", "relationship"},
                "Empathy and relational awareness",
                "The supplied signals repeatedly emphasize emotional connection and relationships.",
            ),
            (
                {"creativity", "self-expression", "imagination"},
                "Creative self-expression",
                "The supplied signals contain themes associated with imagination, creativity, or expression.",
            ),
            (
                {"thinking", "reasoning", "logic", "ideas"},
                "Reflective reasoning",
                "The supplied signals contain recurring themes related to thinking, reasoning, or ideas.",
            ),
            (
                {"career", "purpose", "goal", "work", "responsibility"},
                "Purpose and goal orientation",
                "The supplied signals include themes connected with direction, work, responsibility, or goals.",
            ),
            (
                {"change", "adaptability", "transformation"},
                "Adaptability",
                "The supplied Tarot/palm themes include change or transformation.",
            ),
        ]

        for keywords, title, basis in strength_rules:
            if self._contains_any(combined, keywords):
                strengths.append(
                    {
                        "title": title,
                        "description": basis,
                        "evidence_type": "symbolic_theme",
                    }
                )

        if not strengths:
            strengths.append(
                {
                    "title": "Self-reflection",
                    "description": (
                        "Engaging with the reading can provide a structured "
                        "opportunity to reflect on personal priorities."
                    ),
                    "evidence_type": "general_reflection",
                }
            )

        return strengths[:5]

    # ============================================================
    # DEVELOPMENT AREAS
    # ============================================================

    def _build_development_areas(
        self,
        signals: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        combined = (
            " ".join(signals["line_text"])
            + " "
            + " ".join(signals["tarot_text"])
        ).lower()

        areas: List[Dict[str, Any]] = []

        rules = [
            (
                {"worry", "fear", "anxious", "restriction", "trapped"},
                "Managing mental pressure",
                "The supplied Tarot themes include restriction, fear, or worry.",
            ),
            (
                {"conflict", "disruption", "tower", "sudden change"},
                "Building flexibility during change",
                "The supplied themes include disruption or significant change.",
            ),
            (
                {"control", "security", "attachment"},
                "Balancing stability with openness",
                "The supplied themes include security, control, or attachment.",
            ),
            (
                {"emotion", "sensitivity", "feeling"},
                "Balancing emotional awareness with clear decisions",
                "The supplied signals emphasize emotional awareness.",
            ),
        ]

        for keywords, title, basis in rules:
            if self._contains_any(combined, keywords):
                areas.append(
                    {
                        "title": title,
                        "description": basis,
                        "evidence_type": "symbolic_theme",
                    }
                )

        if not areas:
            areas.append(
                {
                    "title": "Continued self-observation",
                    "description": (
                        "Track which themes resonate with your real experiences "
                        "rather than treating the reading as a fixed description."
                    ),
                    "evidence_type": "general_reflection",
                }
            )

        return areas[:5]

    # ============================================================
    # BEHAVIORAL INSIGHTS
    # ============================================================

    def _build_behavioral_insights(
        self,
        signals: Dict[str, Any],
    ) -> List[str]:
        combined = (
            " ".join(signals["line_text"])
            + " "
            + " ".join(signals["tarot_text"])
        ).lower()

        insights: List[str] = []

        if self._contains_any(
            combined,
            {"emotion", "relationship", "connection", "empathy"},
        ):
            insights.append(
                "You may place meaningful value on interpersonal connection "
                "and emotional understanding."
            )

        if self._contains_any(
            combined,
            {"thinking", "reasoning", "logic", "ideas"},
        ):
            insights.append(
                "You may benefit from pausing to compare alternatives before "
                "committing to an important decision."
            )

        if self._contains_any(
            combined,
            {"career", "purpose", "goal", "work"},
        ):
            insights.append(
                "Purpose, progress, or meaningful goals may be useful themes "
                "when reviewing your current priorities."
            )

        if self._contains_any(
            combined,
            {"creativity", "self-expression", "imagination"},
        ):
            insights.append(
                "Creative activities may provide a useful channel for "
                "self-expression and reflection."
            )

        if self._contains_any(
            combined,
            {"change", "disruption", "transformation"},
        ):
            insights.append(
                "When circumstances change, deliberately reviewing assumptions "
                "may help you adapt rather than reacting immediately."
            )

        if not insights:
            insights.append(
                "Use the supplied themes as prompts for observing your actual "
                "patterns, preferences, and decisions."
            )

        return insights[:5]

    # ============================================================
    # RECOMMENDATIONS
    # ============================================================

    def _build_recommendations(
        self,
        signals: Dict[str, Any],
        strengths: List[Dict[str, Any]],
        development_areas: List[Dict[str, Any]],
    ) -> List[str]:
        recommendations: List[str] = []

        if strengths:
            recommendations.append(
                "Choose one strength from the profile and identify a real "
                "situation where you can apply it deliberately."
            )

        if development_areas:
            recommendations.append(
                "Select one development area and turn it into a small, "
                "measurable weekly practice."
            )

        if signals["profile_signals"]["interests"]:
            interest = signals["profile_signals"]["interests"][0]
            recommendations.append(
                f"Connect your self-reflection to your stated interest in "
                f"{interest} and record what you learn from the experience."
            )

        if signals["profile_signals"]["spiritual_goals"]:
            goal = signals["profile_signals"]["spiritual_goals"][0]
            recommendations.append(
                f"Use your stated goal of {goal} as a concrete reflection "
                "theme rather than relying on generalized predictions."
            )

        recommendations.append(
            "Review the profile periodically and keep only interpretations "
            "that are consistent with your lived experience."
        )

        return self._unique(recommendations)[:5]

    # ============================================================
    # SCORES
    # ============================================================

    def _calculate_alignment_score(
        self,
        signals: Dict[str, Any],
        profile: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> float:
        evidence_parts: List[float] = []

        if signals["element"]:
            evidence_parts.append(70.0)

        if signals["line_signals"]:
            evidence_parts.append(
                min(100.0, len(signals["line_signals"]) * 18.0)
            )

        if signals["tarot_cards"]:
            evidence_parts.append(
                min(100.0, len(signals["tarot_cards"]) * 22.0)
            )

        interests = signals["profile_signals"]["interests"]
        goals = signals["profile_signals"]["spiritual_goals"]

        if interests or goals:
            combined_profile = " ".join(interests + goals).lower()
            themes = " ".join(
                profile.get("core_traits", [])
            ).lower()

            overlap = sum(
                1
                for token in self._meaningful_tokens(combined_profile)
                if token in themes
            )

            profile_score = min(100.0, 55.0 + overlap * 10.0)
            evidence_parts.append(profile_score)

        if not evidence_parts:
            return 50.0

        return self._round_score(
            sum(evidence_parts) / len(evidence_parts)
        )

    @staticmethod
    def _meaningful_tokens(text: str) -> List[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "your",
            "you",
            "goal",
            "goals",
            "interest",
            "interests",
        }

        return [
            token
            for token in text.split()
            if len(token) >= 4 and token not in stop_words
        ]

    def _calculate_confidence(self, signals: Dict[str, Any]) -> float:
        components: List[float] = []

        line_signals = signals["line_signals"]

        if line_signals:
            line_quality: List[float] = []

            for line in line_signals.values():
                values = []

                for key in (
                    "clarity_score",
                    "support_ratio",
                    "continuity_proxy",
                ):
                    value = line.get(key)
                    if isinstance(value, (int, float)):
                        values.append(self._clamp(float(value), 0.0, 1.0))

                if values:
                    line_quality.append(sum(values) / len(values))

            if line_quality:
                components.append(
                    (sum(line_quality) / len(line_quality)) * 100.0
                )

        if signals["tarot_cards"]:
            complete_cards = 0

            for card in signals["tarot_cards"]:
                if (
                    card.get("name")
                    and card.get("orientation")
                    and card.get("interpretation")
                ):
                    complete_cards += 1

            components.append(
                (complete_cards / len(signals["tarot_cards"])) * 100.0
            )

        if signals["profile_signals"]["interests"] or signals[
            "profile_signals"
        ]["spiritual_goals"]:
            components.append(75.0)

        if not components:
            return 50.0

        return self._round_score(
            sum(components) / len(components)
        )

    # ============================================================
    # UTILITY
    # ============================================================

    @staticmethod
    def _unique(items: List[str]) -> List[str]:
        seen = set()
        result = []

        for item in items:
            normalized = item.strip().lower()

            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            result.append(item.strip())

        return result


personality_engine = PersonalityIntelligenceEngine()
