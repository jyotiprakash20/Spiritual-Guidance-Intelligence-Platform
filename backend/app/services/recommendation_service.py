"""
M3.3 — Recommendation Intelligence Engine

Generates personalized, evidence-linked recommendations from:
- Palmistry feature signals
- Tarot spread themes
- M3.2 personality intelligence
- Supplied user context

This is a deterministic/rule-based recommendation layer.
No ML training or fine-tuning is required.

Important:
Palmistry and Tarot outputs are treated as reflective/symbolic inputs,
not scientifically validated predictions or diagnoses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class RecommendationIntelligenceEngine:
    """Build reflective, personalized recommendations from reading evidence."""

    VERSION = "M3.3"

    DISCLAIMER = (
        "These recommendations are reflective suggestions derived from "
        "symbolic palm/Tarot signals and supplied profile context. They are "
        "not predictions, medical advice, financial advice, or scientifically "
        "validated behavioral prescriptions."
    )

    def __init__(self) -> None:
        self._theme_keywords = {
            "creativity": {
                "creative",
                "creativity",
                "expression",
                "imagination",
                "art",
                "nurturing",
                "growth",
            },
            "emotional_awareness": {
                "emotion",
                "emotional",
                "compassion",
                "empathy",
                "relationships",
                "connection",
                "feelings",
                "sensitivity",
            },
            "curiosity": {
                "curiosity",
                "curious",
                "observation",
                "information",
                "learning",
                "communication",
                "seeking",
            },
            "purpose": {
                "purpose",
                "progress",
                "career",
                "direction",
                "responsibility",
                "goals",
                "life-path",
                "work",
            },
            "reflection": {
                "reflection",
                "reflective",
                "reasoning",
                "thinking",
                "self-awareness",
                "balance",
            },
            "connection": {
                "relationship",
                "relationships",
                "connection",
                "community",
                "social",
                "nurturing",
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        palm_features: Optional[Dict[str, Any]] = None,
        tarot_data: Optional[Dict[str, Any]] = None,
        personality_data: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate personalized recommendations.

        The method intentionally relies only on supplied structured evidence.
        Missing inputs are handled gracefully.
        """
        palm_features = palm_features or {}
        tarot_data = tarot_data or {}
        personality_data = personality_data or {}
        user_context = user_context or {}

        signals = self._extract_signals(
            palm_features=palm_features,
            tarot_data=tarot_data,
            personality_data=personality_data,
            user_context=user_context,
        )

        themes = self._rank_themes(signals)

        recommendations = self._build_recommendations(
            themes=themes,
            signals=signals,
            user_context=user_context,
        )

        category_groups = self._build_category_groups(
            recommendations=recommendations
        )

        priority = self._build_priority_items(
            recommendations=recommendations
        )

        confidence = self._calculate_confidence(
            signals=signals,
            recommendation_count=len(recommendations),
        )

        return {
            "status": "success",
            "engine": "rule_based_recommendation_intelligence",
            "version": self.VERSION,
            "disclaimer": self.DISCLAIMER,
            "top_themes": [
                {
                    "theme": theme,
                    "score": round(score, 2),
                    "evidence": evidence,
                }
                for theme, score, evidence in themes[:5]
            ],
            "recommendations": recommendations,
            "recommendations_by_category": category_groups,
            "priority_recommendations": priority,
            "recommendation_count": len(recommendations),
            "analysis_confidence": round(confidence, 2),
            "evidence": {
                "palm_signals": signals["palm_signals"],
                "tarot_signals": signals["tarot_signals"],
                "personality_signals": signals["personality_signals"],
                "profile_signals": signals["profile_signals"],
            },
        }

    # ------------------------------------------------------------------
    # Signal extraction
    # ------------------------------------------------------------------

    def _extract_signals(
        self,
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
        personality_data: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        text_parts: List[str] = []

        hand_type = palm_features.get("hand_type") or {}
        palm_structure = palm_features.get("palm_structure") or {}
        major_lines = palm_features.get("major_lines") or {}
        mounts = palm_features.get("mounts") or {}

        if isinstance(hand_type, dict):
            for key in ("type", "name", "element", "description"):
                value = hand_type.get(key)
                if value:
                    text_parts.append(str(value))

        if isinstance(palm_features.get("element"), str):
            text_parts.append(palm_features["element"])

        for line_name, line_data in major_lines.items():
            if not isinstance(line_data, dict):
                continue

            insight = line_data.get("insight")
            characteristic_interpretation = line_data.get(
                "characteristic_interpretation"
            )

            if insight:
                text_parts.append(str(insight))
            if characteristic_interpretation:
                text_parts.append(str(characteristic_interpretation))

        if isinstance(mounts, dict):
            for mount_name, mount_data in mounts.items():
                if isinstance(mount_data, dict):
                    for key in ("interpretation", "meaning", "description"):
                        value = mount_data.get(key)
                        if value:
                            text_parts.append(str(value))

        palm_text = " ".join(text_parts).lower()

        tarot_cards = self._extract_tarot_cards(tarot_data)
        tarot_text_parts: List[str] = []

        for card in tarot_cards:
            for key in (
                "name",
                "card_name",
                "interpretation",
                "meaning",
                "meaning_upright",
                "meaning_reversed",
                "orientation",
                "position",
            ):
                value = card.get(key)
                if value:
                    tarot_text_parts.append(str(value))

        tarot_text = " ".join(tarot_text_parts).lower()

        personality_profile = personality_data.get("personality_profile") or {}
        strengths = personality_data.get("strengths") or []
        development_areas = personality_data.get("development_areas") or []
        behavioral_insights = personality_data.get("behavioral_insights") or []

        personality_text_parts: List[str] = []

        if isinstance(personality_profile, dict):
            summary = personality_profile.get("summary")
            if summary:
                personality_text_parts.append(str(summary))

            core_traits = personality_profile.get("core_traits") or []
            personality_text_parts.extend(str(item) for item in core_traits)

            dimensions = personality_profile.get("behavioral_dimensions") or {}
            if isinstance(dimensions, dict):
                personality_text_parts.extend(
                    str(value) for value in dimensions.values() if value
                )

        personality_text_parts.extend(self._item_text(strengths))
        personality_text_parts.extend(self._item_text(development_areas))
        personality_text_parts.extend(
            str(item) for item in behavioral_insights if item
        )

        personality_text = " ".join(personality_text_parts).lower()

        profile_text_parts: List[str] = []

        interests = user_context.get("interests")
        spiritual_goals = user_context.get("spiritual_goals")
        age_group = user_context.get("age_group")

        profile_text_parts.extend(self._flatten_context_value(interests))
        profile_text_parts.extend(self._flatten_context_value(spiritual_goals))

        if age_group:
            profile_text_parts.append(str(age_group))

        profile_text = " ".join(profile_text_parts).lower()

        return {
            "palm_signals": {
                "hand_type": self._safe_value(
                    hand_type,
                    ("type", "name", "element"),
                ),
                "element": palm_features.get("element"),
                "major_line_count": len(major_lines)
                if isinstance(major_lines, dict)
                else 0,
                "mount_count": len(mounts)
                if isinstance(mounts, dict)
                else 0,
                "is_finger_long": palm_structure.get("is_finger_long"),
                "is_palm_square": palm_structure.get("is_palm_square"),
                "themes_text": palm_text[:1500],
            },
            "tarot_signals": {
                "spread_type": tarot_data.get("spread_type"),
                "card_count": len(tarot_cards),
                "cards": [
                    {
                        "name": card.get("name")
                        or card.get("card_name"),
                        "orientation": card.get("orientation"),
                        "position": card.get("position"),
                    }
                    for card in tarot_cards
                ],
                "themes_text": tarot_text[:2000],
            },
            "personality_signals": {
                "alignment_score": personality_data.get("alignment_score"),
                "analysis_confidence": personality_data.get(
                    "analysis_confidence"
                ),
                "strength_count": len(strengths)
                if isinstance(strengths, list)
                else 0,
                "development_area_count": len(development_areas)
                if isinstance(development_areas, list)
                else 0,
                "themes_text": personality_text[:2000],
            },
            "profile_signals": {
                "interests": self._normalize_context_value(interests),
                "spiritual_goals": self._normalize_context_value(
                    spiritual_goals
                ),
                "age_group": age_group,
                "themes_text": profile_text[:1000],
            },
            "_text": {
                "palm": palm_text,
                "tarot": tarot_text,
                "personality": personality_text,
                "profile": profile_text,
            },
        }

    # ------------------------------------------------------------------
    # Theme scoring
    # ------------------------------------------------------------------

    def _rank_themes(
        self,
        signals: Dict[str, Any],
    ) -> List[tuple[str, float, List[str]]]:
        text = signals["_text"]

        ranked: List[tuple[str, float, List[str]]] = []

        source_weights = {
            "palm": 1.0,
            "tarot": 1.0,
            "personality": 1.25,
            "profile": 1.15,
        }

        for theme, keywords in self._theme_keywords.items():
            score = 0.0
            evidence: List[str] = []

            for source, source_text in text.items():
                if not source_text:
                    continue

                matches = [
                    keyword
                    for keyword in keywords
                    if keyword in source_text
                ]

                if matches:
                    unique_matches = list(dict.fromkeys(matches))
                    contribution = min(
                        len(unique_matches) * 8.0,
                        30.0,
                    ) * source_weights.get(source, 1.0)

                    score += contribution

                    evidence.append(
                        f"{source}: {', '.join(unique_matches[:4])}"
                    )

            if score > 0:
                ranked.append(
                    (
                        theme,
                        min(score, 100.0),
                        evidence,
                    )
                )

        ranked.sort(key=lambda item: item[1], reverse=True)

        return ranked

    # ------------------------------------------------------------------
    # Recommendation construction
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        themes: List[tuple[str, float, List[str]]],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        theme_handlers = {
            "creativity": self._creative_recommendations,
            "emotional_awareness": self._emotional_recommendations,
            "curiosity": self._curiosity_recommendations,
            "purpose": self._purpose_recommendations,
            "reflection": self._reflection_recommendations,
            "connection": self._connection_recommendations,
        }

        for theme, score, evidence in themes[:6]:
            handler = theme_handlers.get(theme)

            if not handler:
                continue

            items = handler(
                score=score,
                evidence=evidence,
                signals=signals,
                user_context=user_context,
            )

            recommendations.extend(items)

        # Remove duplicate recommendation IDs while preserving order.
        unique: Dict[str, Dict[str, Any]] = {}

        for item in recommendations:
            recommendation_id = item["id"]
            if recommendation_id not in unique:
                unique[recommendation_id] = item

        result = list(unique.values())

        result.sort(
            key=lambda item: (
                item.get("priority_score", 0),
                item.get("evidence_strength", 0),
            ),
            reverse=True,
        )

        # Keep the API response focused.
        return result[:12]

    def _creative_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "creative_expression",
                "Personal Development",
                "Create a small weekly outlet for creative expression.",
                "Set aside 30–60 minutes each week for writing, design, photography, music, drawing, building, or another activity you genuinely enjoy.",
                score,
                evidence,
            ),
            self._make_recommendation(
                "creative_project",
                "Personal Development",
                "Turn one creative interest into a small project.",
                "Choose a project that can be completed in a few weeks and record what you learn rather than focusing only on the final result.",
                score - 3,
                evidence,
            ),
        ]

    def _emotional_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "decision_pause",
                "Personal Development",
                "Use a short pause before important emotional decisions.",
                "When a decision feels emotionally intense, write down the options, the immediate feeling, and the practical consequences before deciding.",
                score,
                evidence,
            ),
            self._make_recommendation(
                "reflection_journal",
                "Wellness & Reflection",
                "Keep a brief reflection journal.",
                "Record one meaningful event, your reaction to it, and one thing you would repeat or change.",
                score - 2,
                evidence,
            ),
        ]

    def _curiosity_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "learning_goal",
                "Learning & Growth",
                "Choose one focused learning goal.",
                "Pick one topic and define a small weekly target such as completing a lesson, solving practice problems, or building a feature.",
                score,
                evidence,
            ),
            self._make_recommendation(
                "question_log",
                "Learning & Growth",
                "Maintain a question-and-discovery log.",
                "Write down questions that arise while learning and revisit them at the end of each week.",
                score - 3,
                evidence,
            ),
        ]

    def _purpose_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "goal_alignment",
                "Goals & Career",
                "Connect weekly tasks to one meaningful goal.",
                "Choose one current goal and identify the smallest useful action you can complete this week.",
                score,
                evidence,
            ),
            self._make_recommendation(
                "progress_review",
                "Goals & Career",
                "Review progress regularly instead of relying on predictions.",
                "At the end of each week, record what moved forward, what stalled, and what you want to change next week.",
                score - 2,
                evidence,
            ),
        ]

    def _reflection_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "weekly_reflection",
                "Wellness & Reflection",
                "Use a short weekly self-reflection.",
                "Review your priorities, recent decisions, and lessons learned, then choose one practical adjustment.",
                score,
                evidence,
            ),
        ]

    def _connection_recommendations(
        self,
        score: float,
        evidence: List[str],
        signals: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            self._make_recommendation(
                "relationship_checkin",
                "Relationships",
                "Make time for a meaningful conversation.",
                "Reach out to someone important to you and have a conversation without multitasking or rushing.",
                score,
                evidence,
            ),
            self._make_recommendation(
                "community_activity",
                "Relationships",
                "Try one constructive community activity.",
                "Choose a club, group, collaborative project, or shared activity that matches an existing interest.",
                score - 3,
                evidence,
            ),
        ]

    # ------------------------------------------------------------------
    # Profile-aware recommendation additions
    # ------------------------------------------------------------------

    def _apply_profile_personalization(
        self,
        recommendations: List[Dict[str, Any]],
        user_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        interests = self._normalize_context_value(
            user_context.get("interests")
        )

        if not interests:
            return recommendations

        interest_text = ", ".join(interests)

        for item in recommendations:
            item["personalization_note"] = (
                f"Where practical, connect this recommendation with "
                f"your stated interest in {interest_text}."
            )

        return recommendations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_recommendation(
        self,
        recommendation_id: str,
        category: str,
        title: str,
        action: str,
        priority_score: float,
        evidence: List[str],
    ) -> Dict[str, Any]:
        return {
            "id": recommendation_id,
            "category": category,
            "title": title,
            "action": action,
            "priority_score": round(
                max(0.0, min(priority_score, 100.0)),
                2,
            ),
            "evidence_strength": round(
                min(100.0, 35.0 + len(evidence) * 15.0),
                2,
            ),
            "evidence": evidence[:5],
        }

    def _build_category_groups(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}

        for recommendation in recommendations:
            category = recommendation["category"]
            groups.setdefault(category, []).append(recommendation)

        return groups

    def _build_priority_items(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "priority_score": item["priority_score"],
            }
            for item in recommendations[:5]
        ]

    def _calculate_confidence(
        self,
        signals: Dict[str, Any],
        recommendation_count: int,
    ) -> float:
        evidence_sources = 0

        for source_name in (
            "palm_signals",
            "tarot_signals",
            "personality_signals",
            "profile_signals",
        ):
            source = signals.get(source_name) or {}

            if source_name == "palm_signals":
                if source.get("major_line_count", 0) > 0 or source.get(
                    "element"
                ):
                    evidence_sources += 1

            elif source_name == "tarot_signals":
                if source.get("card_count", 0) > 0:
                    evidence_sources += 1

            elif source_name == "personality_signals":
                if source.get("strength_count", 0) > 0 or source.get(
                    "alignment_score"
                ) is not None:
                    evidence_sources += 1

            elif source_name == "profile_signals":
                if source.get("interests") or source.get("spiritual_goals"):
                    evidence_sources += 1

        base = 45.0 + evidence_sources * 10.0
        variety_bonus = min(recommendation_count * 1.5, 10.0)

        return min(90.0, base + variety_bonus)

    def _extract_tarot_cards(
        self,
        tarot_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        cards = tarot_data.get("cards")

        if isinstance(cards, list):
            return [
                card
                for card in cards
                if isinstance(card, dict)
            ]

        # Some service outputs may wrap the cards differently.
        spread = tarot_data.get("spread")

        if isinstance(spread, list):
            return [
                card
                for card in spread
                if isinstance(card, dict)
            ]

        return []

    @staticmethod
    def _item_text(items: Any) -> List[str]:
        if not isinstance(items, list):
            return []

        result: List[str] = []

        for item in items:
            if isinstance(item, dict):
                for key in (
                    "title",
                    "description",
                    "action",
                    "recommendation",
                ):
                    value = item.get(key)
                    if value:
                        result.append(str(value))
            elif item:
                result.append(str(item))

        return result

    @staticmethod
    def _flatten_context_value(value: Any) -> List[str]:
        if value is None:
            return []

        if isinstance(value, list):
            return [
                str(item)
                for item in value
                if item is not None and str(item).strip()
            ]

        if isinstance(value, dict):
            return [
                str(item)
                for item in value.values()
                if item is not None and str(item).strip()
            ]

        return [str(value)]

    @classmethod
    def _normalize_context_value(cls, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, list):
            return [
                str(item)
                for item in value
                if item is not None and str(item).strip()
            ]

        if isinstance(value, dict):
            return {
                str(key): item
                for key, item in value.items()
            }

        return [str(value)]

    @staticmethod
    def _safe_value(
        data: Dict[str, Any],
        keys: tuple[str, ...],
    ) -> Any:
        for key in keys:
            value = data.get(key)
            if value:
                return value

        return None


recommendation_engine = RecommendationIntelligenceEngine()
