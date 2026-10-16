"""
M3.4 — Life Trends & Opportunities Intelligence Engine

Builds reflective trend signals from the existing:
- Palmistry feature evidence
- Tarot spread themes
- M3.2 personality intelligence
- M3.3 recommendations
- Supplied user context

This is a deterministic/rule-based interpretation layer.
No ML training or fine-tuning is required.

Important:
The engine does NOT predict a person's future. It identifies recurring
themes and possible areas for reflection based on supplied symbolic evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class LifeTrendsIntelligenceEngine:
    VERSION = "M3.4"

    DISCLAIMER = (
        "These trends are reflective themes derived from symbolic palm/Tarot "
        "signals, personality outputs, recommendations, and supplied profile "
        "context. They are not predictions or scientifically validated "
        "forecasts of future events."
    )

    AREAS = (
        "Career & Direction",
        "Personal Growth",
        "Relationships",
        "Creativity & Expression",
        "Learning & Exploration",
        "Opportunities & New Beginnings",
    )

    def analyze(
        self,
        palm_features: Optional[Dict[str, Any]] = None,
        tarot_data: Optional[Dict[str, Any]] = None,
        personality_data: Optional[Dict[str, Any]] = None,
        recommendation_data: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        palm_features = palm_features or {}
        tarot_data = tarot_data or {}
        personality_data = personality_data or {}
        recommendation_data = recommendation_data or {}
        user_context = user_context or {}

        signals = self._extract_signals(
            palm_features,
            tarot_data,
            personality_data,
            recommendation_data,
            user_context,
        )

        trends = self._build_trends(signals)
        opportunities = self._build_opportunities(signals, trends)
        reflection_areas = self._build_reflection_areas(signals, trends)

        return {
            "status": "success",
            "engine": "rule_based_life_trends_intelligence",
            "version": self.VERSION,
            "disclaimer": self.DISCLAIMER,
            "trend_summary": self._build_summary(trends),
            "life_trends": trends,
            "opportunities": opportunities,
            "reflection_areas": reflection_areas,
            "trend_count": len(trends),
            "opportunity_count": len(opportunities),
            "analysis_confidence": self._calculate_confidence(signals, trends),
            "evidence": signals,
        }

    # ------------------------------------------------------------------
    # Evidence extraction
    # ------------------------------------------------------------------

    def _extract_signals(
        self,
        palm_features: Dict[str, Any],
        tarot_data: Dict[str, Any],
        personality_data: Dict[str, Any],
        recommendation_data: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        palm_text = self._palm_text(palm_features)
        tarot_cards = self._tarot_cards(tarot_data)
        tarot_text = self._tarot_text(tarot_cards)

        personality_text = self._personality_text(personality_data)

        recommendation_text = self._recommendation_text(
            recommendation_data
        )

        interests = self._to_list(user_context.get("interests"))
        goals = self._to_list(user_context.get("spiritual_goals"))

        profile_text = " ".join(
            interests + goals + [str(user_context.get("age_group") or "")]
        ).lower()

        return {
            "palm": {
                "text": palm_text[:3000],
                "major_line_count": self._major_line_count(palm_features),
                "mount_count": self._mount_count(palm_features),
                "element": palm_features.get("element"),
            },
            "tarot": {
                "spread_type": tarot_data.get("spread_type"),
                "card_count": len(tarot_cards),
                "cards": [
                    {
                        "name": card.get("name") or card.get("card_name"),
                        "orientation": card.get("orientation"),
                        "position": card.get("position"),
                    }
                    for card in tarot_cards
                ],
                "text": tarot_text[:3500],
            },
            "personality": {
                "text": personality_text[:3500],
                "alignment_score": personality_data.get("alignment_score"),
                "analysis_confidence": personality_data.get(
                    "analysis_confidence"
                ),
            },
            "recommendations": {
                "text": recommendation_text[:3500],
                "count": recommendation_data.get("recommendation_count", 0),
            },
            "profile": {
                "interests": interests,
                "spiritual_goals": goals,
                "age_group": user_context.get("age_group"),
                "text": profile_text[:1500],
            },
        }

    # ------------------------------------------------------------------
    # Trend construction
    # ------------------------------------------------------------------

    def _build_trends(
        self,
        signals: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        source_text = {
            "palm": signals["palm"]["text"].lower(),
            "tarot": signals["tarot"]["text"].lower(),
            "personality": signals["personality"]["text"].lower(),
            "recommendations": signals["recommendations"]["text"].lower(),
            "profile": signals["profile"]["text"].lower(),
        }

        definitions = [
            (
                "Career & Direction",
                {
                    "career",
                    "direction",
                    "life-path",
                    "purpose",
                    "work",
                    "goal",
                    "responsibility",
                    "progress",
                },
                "Themes related to direction, purpose, responsibility, "
                "and progress may be useful when reviewing current goals.",
            ),
            (
                "Personal Growth",
                {
                    "growth",
                    "reflection",
                    "self-awareness",
                    "development",
                    "balance",
                    "learning",
                    "resilience",
                },
                "The supplied signals repeatedly contain themes that can "
                "support deliberate reflection and personal development.",
            ),
            (
                "Relationships",
                {
                    "relationship",
                    "relationships",
                    "connection",
                    "empathy",
                    "compassion",
                    "emotional",
                    "nurturing",
                },
                "Emotional awareness and connection appear as recurring "
                "themes worth reflecting on in interpersonal situations.",
            ),
            (
                "Creativity & Expression",
                {
                    "creativity",
                    "creative",
                    "expression",
                    "imagination",
                    "recognition",
                    "art",
                    "building",
                },
                "Creative expression appears as a recurring theme across "
                "the supplied symbolic and personality signals.",
            ),
            (
                "Learning & Exploration",
                {
                    "curiosity",
                    "curious",
                    "information",
                    "observation",
                    "communication",
                    "reasoning",
                    "thinking",
                    "seeking",
                },
                "Curiosity, information gathering, and reasoning can provide "
                "useful themes for structured exploration.",
            ),
            (
                "Opportunities & New Beginnings",
                {
                    "new beginning",
                    "new opportunity",
                    "opportunity",
                    "beginning",
                    "transition",
                    "completion",
                    "achievement",
                    "new cycle",
                },
                "The supplied signals include transition or new-beginning "
                "themes that can be used as prompts for practical planning.",
            ),
        ]

        trends: List[Dict[str, Any]] = []

        for area, keywords, description in definitions:
            score = 0.0
            evidence: List[str] = []

            source_weights = {
                "palm": 1.0,
                "tarot": 1.15,
                "personality": 1.25,
                "recommendations": 1.15,
                "profile": 0.9,
            }

            for source, text in source_text.items():
                if not text:
                    continue

                matches = [
                    keyword for keyword in keywords if keyword in text
                ]

                if matches:
                    matches = list(dict.fromkeys(matches))
                    contribution = min(
                        len(matches) * 7.5,
                        30.0,
                    ) * source_weights[source]

                    score += contribution
                    evidence.append(
                        f"{source}: {', '.join(matches[:5])}"
                    )

            if score > 0:
                trends.append(
                    {
                        "area": area,
                        "trend_score": round(min(score, 100.0), 2),
                        "description": description,
                        "evidence": evidence[:6],
                        "interpretation": self._trend_interpretation(
                            area
                        ),
                    }
                )

        trends.sort(
            key=lambda item: item["trend_score"],
            reverse=True,
        )

        return trends

    def _trend_interpretation(self, area: str) -> str:
        interpretations = {
            "Career & Direction": (
                "Use this theme to review goals, responsibilities, "
                "skills, and practical next steps."
            ),
            "Personal Growth": (
                "Use this theme to identify one behavior or habit that "
                "could be improved through a small repeatable practice."
            ),
            "Relationships": (
                "Use this theme to reflect on communication, boundaries, "
                "empathy, and meaningful connections."
            ),
            "Creativity & Expression": (
                "Use this theme to create or build something tangible "
                "rather than treating the symbolic signal as a prediction."
            ),
            "Learning & Exploration": (
                "Use this theme to choose a focused topic and explore it "
                "through deliberate practice or research."
            ),
            "Opportunities & New Beginnings": (
                "Use this theme to examine real opportunities and verify "
                "their practical details before acting."
            ),
        }

        return interpretations.get(area, "")

    # ------------------------------------------------------------------
    # Opportunities
    # ------------------------------------------------------------------

    def _build_opportunities(
        self,
        signals: Dict[str, Any],
        trends: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        opportunities: List[Dict[str, Any]] = []

        trend_map = {
            item["area"]: item
            for item in trends
        }

        if "Career & Direction" in trend_map:
            opportunities.append(
                self._opportunity(
                    "career_goal_review",
                    "Career & Direction",
                    "Review one current career or academic goal.",
                    "Identify the next concrete skill, task, or milestone "
                    "that would move the goal forward.",
                    trend_map["Career & Direction"],
                )
            )

        if "Learning & Exploration" in trend_map:
            opportunities.append(
                self._opportunity(
                    "focused_learning",
                    "Learning & Exploration",
                    "Start a focused learning sprint.",
                    "Choose one topic connected to your current interests "
                    "and work on it consistently for a defined period.",
                    trend_map["Learning & Exploration"],
                )
            )

        if "Creativity & Expression" in trend_map:
            opportunities.append(
                self._opportunity(
                    "creative_project",
                    "Creativity & Expression",
                    "Turn a creative interest into a small project.",
                    "Create something that can be completed and reviewed, "
                    "such as a design, article, prototype, or artwork.",
                    trend_map["Creativity & Expression"],
                )
            )

        if "Relationships" in trend_map:
            opportunities.append(
                self._opportunity(
                    "connection_activity",
                    "Relationships",
                    "Strengthen one meaningful connection.",
                    "Choose one person or community connection and invest "
                    "some focused time in communication.",
                    trend_map["Relationships"],
                )
            )

        if "Personal Growth" in trend_map:
            opportunities.append(
                self._opportunity(
                    "growth_practice",
                    "Personal Growth",
                    "Choose one small personal-development practice.",
                    "Make the practice measurable and review it weekly "
                    "rather than relying on broad predictions.",
                    trend_map["Personal Growth"],
                )
            )

        if "Opportunities & New Beginnings" in trend_map:
            opportunities.append(
                self._opportunity(
                    "opportunity_check",
                    "Opportunities & New Beginnings",
                    "Review a real opportunity carefully.",
                    "Compare alternatives, verify important information, "
                    "and identify practical risks before committing.",
                    trend_map["Opportunities & New Beginnings"],
                )
            )

        return opportunities[:6]

    def _opportunity(
        self,
        opportunity_id: str,
        category: str,
        title: str,
        action: str,
        trend: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "id": opportunity_id,
            "category": category,
            "title": title,
            "action": action,
            "theme_score": trend["trend_score"],
            "evidence": trend["evidence"],
        }

    # ------------------------------------------------------------------
    # Reflection areas
    # ------------------------------------------------------------------

    def _build_reflection_areas(
        self,
        signals: Dict[str, Any],
        trends: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        areas: List[Dict[str, Any]] = []

        tarot_text = signals["tarot"]["text"].lower()
        personality_text = signals["personality"]["text"].lower()

        if (
            "confusion" in tarot_text
            or "poor judgment" in tarot_text
            or "clarity" in tarot_text
        ):
            areas.append(
                {
                    "area": "Decision Clarity",
                    "prompt": (
                        "Before an important decision, verify information, "
                        "compare alternatives, and separate immediate emotion "
                        "from practical consequences."
                    ),
                    "evidence": "Tarot interpretation contains clarity or "
                    "decision-related themes.",
                }
            )

        if (
            "emotional awareness" in personality_text
            or "empathy" in personality_text
        ):
            areas.append(
                {
                    "area": "Emotional Balance",
                    "prompt": (
                        "Notice emotional reactions while also considering "
                        "evidence and practical consequences."
                    ),
                    "evidence": "Personality output contains empathy or "
                    "emotional-awareness themes.",
                }
            )

        if not areas:
            areas.append(
                {
                    "area": "Self-Reflection",
                    "prompt": (
                        "Review which themes from the reading match your "
                        "actual experience and keep only what remains useful."
                    ),
                    "evidence": "General reflective safeguard.",
                }
            )

        return areas[:4]

    # ------------------------------------------------------------------
    # Summary and confidence
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        trends: List[Dict[str, Any]],
    ) -> str:
        if not trends:
            return (
                "The supplied reading does not contain enough recurring "
                "signals to identify a focused trend theme."
            )

        top = [item["area"] for item in trends[:3]]

        if len(top) == 1:
            joined = top[0]
        elif len(top) == 2:
            joined = f"{top[0]} and {top[1]}"
        else:
            joined = f"{top[0]}, {top[1]}, and {top[2]}"

        return (
            f"The strongest recurring reflective themes in the supplied "
            f"evidence are {joined}. These are themes for review and "
            f"planning, not predictions of future events."
        )

    def _calculate_confidence(
        self,
        signals: Dict[str, Any],
        trends: List[Dict[str, Any]],
    ) -> float:
        available = 0

        if signals["palm"]["major_line_count"] > 0:
            available += 1

        if signals["tarot"]["card_count"] > 0:
            available += 1

        if signals["personality"]["text"]:
            available += 1

        if signals["recommendations"]["count"]:
            available += 1

        if signals["profile"]["text"]:
            available += 1

        base = 45.0 + available * 8.0
        trend_bonus = min(len(trends) * 2.0, 10.0)

        return round(min(90.0, base + trend_bonus), 2)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _palm_text(self, palm_features: Dict[str, Any]) -> str:
        parts: List[str] = []

        element = palm_features.get("element")
        if element:
            parts.append(str(element))

        hand_type = palm_features.get("hand_type") or {}
        if isinstance(hand_type, dict):
            parts.extend(
                str(hand_type.get(key))
                for key in ("type", "name", "element", "description")
                if hand_type.get(key)
            )

        lines = palm_features.get("major_lines") or {}

        if isinstance(lines, dict):
            for data in lines.values():
                if not isinstance(data, dict):
                    continue

                for key in (
                    "insight",
                    "characteristic_interpretation",
                ):
                    value = data.get(key)
                    if value:
                        parts.append(str(value))

        return " ".join(parts).lower()

    def _tarot_cards(
        self,
        tarot_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        cards = tarot_data.get("cards")

        if isinstance(cards, list):
            return [
                card for card in cards if isinstance(card, dict)
            ]

        spread = tarot_data.get("spread")

        if isinstance(spread, list):
            return [
                card for card in spread if isinstance(card, dict)
            ]

        return []

    def _tarot_text(
        self,
        cards: List[Dict[str, Any]],
    ) -> str:
        parts: List[str] = []

        for card in cards:
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
                    parts.append(str(value))

        return " ".join(parts).lower()

    def _personality_text(
        self,
        personality_data: Dict[str, Any],
    ) -> str:
        parts: List[str] = []

        profile = personality_data.get("personality_profile") or {}

        if isinstance(profile, dict):
            if profile.get("summary"):
                parts.append(str(profile["summary"]))

            parts.extend(
                str(item)
                for item in (profile.get("core_traits") or [])
                if item
            )

            dimensions = profile.get("behavioral_dimensions") or {}

            if isinstance(dimensions, dict):
                parts.extend(
                    str(value)
                    for value in dimensions.values()
                    if value
                )

        for key in (
            "strengths",
            "development_areas",
            "behavioral_insights",
            "personal_development_recommendations",
        ):
            value = personality_data.get(key)

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        parts.extend(
                            str(item.get(field))
                            for field in (
                                "title",
                                "description",
                                "action",
                            )
                            if item.get(field)
                        )
                    elif item:
                        parts.append(str(item))

        return " ".join(parts).lower()

    def _recommendation_text(
        self,
        recommendation_data: Dict[str, Any],
    ) -> str:
        parts: List[str] = []

        recommendations = recommendation_data.get("recommendations") or []

        if isinstance(recommendations, list):
            for item in recommendations:
                if isinstance(item, dict):
                    parts.extend(
                        str(item.get(key))
                        for key in ("category", "title", "action")
                        if item.get(key)
                    )

        return " ".join(parts).lower()

    @staticmethod
    def _major_line_count(
        palm_features: Dict[str, Any],
    ) -> int:
        lines = palm_features.get("major_lines")
        return len(lines) if isinstance(lines, dict) else 0

    @staticmethod
    def _mount_count(
        palm_features: Dict[str, Any],
    ) -> int:
        mounts = palm_features.get("mounts")
        return len(mounts) if isinstance(mounts, dict) else 0

    @staticmethod
    def _to_list(value: Any) -> List[str]:
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


life_trends_engine = LifeTrendsIntelligenceEngine()
