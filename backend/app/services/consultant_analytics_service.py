
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any


class ConsultantAnalyticsService:
    """Summarize saved reading data for an authorized consultant."""

    VERSION = "2.0.0"

    READING_TYPES = ("PALMISTRY", "TAROT", "SYNTHESIZED")

    def _as_dict(self, value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    def _normalize_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned[:200] if cleaned else None

    def _extract_terms(self, value: Any) -> list[str]:
        terms = []

        if isinstance(value, str):
            term = self._normalize_text(value)
            if term:
                terms.append(term)

        elif isinstance(value, list):
            for item in value:
                terms.extend(self._extract_terms(item))

        elif isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(key).lower()

                if any(token in normalized_key for token in (
                    "id", "score", "confidence", "created_at", "timestamp"
                )):
                    continue

                if isinstance(item, (str, list, dict)):
                    terms.extend(self._extract_terms(item))

        return terms

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(
                    value.strip().replace("Z", "+00:00")
                )
            except ValueError:
                return None

        if not isinstance(value, datetime):
            return None

        # Normalize timestamps so month calculations are consistent.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    @staticmethod
    def _percentage_change(current: int, previous: int) -> float | None:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    def analyze(self, readings: list[dict], client_count: int) -> dict:
        safe_readings = [
            item for item in readings if isinstance(item, dict)
        ]

        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")

        previous_month_date = now.replace(day=1) - timedelta(days=1)
        previous_month = previous_month_date.strftime("%Y-%m")

        type_counts = Counter()
        theme_counts = Counter()
        trend_counts = Counter()
        recommendation_counts = Counter()
        monthly_activity = Counter()
        monthly_scores = {}
        scores = []
        dated_readings = []

        for reading in safe_readings:
            reading_type = str(
                reading.get("reading_type", "UNKNOWN")
            ).upper()
            type_counts[reading_type] += 1

            score = reading.get("overall_insight_score")
            if (
                isinstance(score, (int, float))
                and not isinstance(score, bool)
                and 0 <= float(score) <= 100
            ):
                score = float(score)
                scores.append(score)
            else:
                score = None

            created_at = self._parse_datetime(reading.get("created_at"))
            if created_at:
                month = created_at.strftime("%Y-%m")
                monthly_activity[month] += 1
                dated_readings.append((created_at, reading))

                if score is not None:
                    monthly_scores.setdefault(month, []).append(score)

            analysis = self._as_dict(reading.get("analysis_data"))
            synthesis = self._as_dict(analysis.get("synthesis"))
            intelligence = self._as_dict(synthesis.get("intelligence"))

            personality = self._as_dict(analysis.get("personality_data"))
            recommendations = self._as_dict(analysis.get("recommendations"))
            life_trends = self._as_dict(analysis.get("life_trends"))

            if not personality:
                personality = self._as_dict(
                    intelligence.get("personality_intelligence")
                )
            if not recommendations:
                recommendations = self._as_dict(
                    intelligence.get("recommendation_intelligence")
                )
            if not life_trends:
                life_trends = self._as_dict(
                    intelligence.get("life_trends_intelligence")
                )

            for value in (
                personality.get("strengths"),
                personality.get("development_areas"),
                personality.get("behavioral_insights"),
                synthesis.get("key_themes"),
                synthesis.get("interpretation"),
            ):
                theme_counts.update(self._extract_terms(value))

            for value in (
                life_trends.get("life_trends"),
                life_trends.get("top_themes"),
                life_trends.get("opportunities"),
                life_trends.get("reflection_areas"),
            ):
                trend_counts.update(self._extract_terms(value))

            for value in (
                recommendations.get("recommendations_by_category"),
                recommendations.get("top_themes"),
                recommendations.get("priority_recommendations"),
            ):
                recommendation_counts.update(self._extract_terms(value))

        def top_items(counter: Counter, limit: int = 10) -> list[dict]:
            return [
                {"label": label, "occurrences": count}
                for label, count in counter.most_common(limit)
            ]

        current_count = monthly_activity[current_month]
        previous_count = monthly_activity[previous_month]

        current_scores = monthly_scores.get(current_month, [])
        previous_scores = monthly_scores.get(previous_month, [])

        current_average = (
            round(sum(current_scores) / len(current_scores), 2)
            if current_scores else None
        )
        previous_average = (
            round(sum(previous_scores) / len(previous_scores), 2)
            if previous_scores else None
        )

        # Include the last six calendar months, including zero-activity months.
        month_keys = []
        month_cursor = now.replace(day=1)

        for offset in range(5, -1, -1):
            year = month_cursor.year
            month = month_cursor.month - offset

            while month <= 0:
                month += 12
                year -= 1

            month_keys.append(f"{year:04d}-{month:02d}")

        monthly_series = [
            {
                "month": month,
                "readings": monthly_activity[month],
                "scored_readings": len(monthly_scores.get(month, [])),
                "average_insight_score": (
                    round(
                        sum(monthly_scores[month])
                        / len(monthly_scores[month]), 2
                    )
                    if monthly_scores.get(month) else None
                ),
            }
            for month in month_keys
        ]

        # Consultation insights summarize observed records, not predictions.
        consultation_insights = {
            "most_common_themes": top_items(theme_counts, 5),
            "frequent_life_trend_topics": top_items(trend_counts, 5),
            "frequent_recommendation_topics": top_items(
                recommendation_counts, 5
            ),
            "reading_type_distribution": {
                reading_type: type_counts[reading_type]
                for reading_type in self.READING_TYPES
            },
            "latest_reading_at": (
                max(
                    (timestamp for timestamp, _ in dated_readings),
                    default=None,
                ).isoformat()
                if dated_readings else None
            ),
        }

        return {
            "status": "success",
            "engine": "ConsultantAnalyticsService",
            "version": self.VERSION,
            "disclaimer": (
                "Analytics summarize saved reading records. Repeated themes "
                "indicate frequency in available data, not proven personality "
                "traits, predictions, or demonstrated guidance effectiveness."
            ),
            "summary": {
                "active_clients": max(0, int(client_count)),
                "total_readings": len(safe_readings),
                "palmistry_readings": type_counts["PALMISTRY"],
                "tarot_readings": type_counts["TAROT"],
                "synthesized_readings": type_counts["SYNTHESIZED"],
                "other_readings": sum(
                    count for reading_type, count in type_counts.items()
                    if reading_type not in self.READING_TYPES
                ),
                "average_insight_score": (
                    round(sum(scores) / len(scores), 2) if scores else None
                ),
                "scored_readings": len(scores),
                "readings_with_timestamps": len(dated_readings),
            },
            "common_themes": top_items(theme_counts),
            "life_trend_terms": top_items(trend_counts),
            "recommendation_terms": top_items(recommendation_counts),
            "monthly_activity": monthly_series,

            "user_trends": {
                "current_month": current_month,
                "previous_month": previous_month,
                "current_month_readings": current_count,
                "previous_month_readings": previous_count,
                "reading_count_change_percent": self._percentage_change(
                    current_count, previous_count
                ),
                "current_month_average_insight_score": current_average,
                "previous_month_average_insight_score": previous_average,
                "insight_score_change": (
                    round(current_average - previous_average, 2)
                    if current_average is not None
                    and previous_average is not None
                    else None
                ),
                "monthly_activity": monthly_series,
            },

            "guidance_effectiveness": {
                "status": "insufficient_outcome_data",
                "average_insight_score": (
                    round(sum(scores) / len(scores), 2) if scores else None
                ),
                "scored_readings": len(scores),
                "client_feedback_count": 0,
                "measured_outcome_count": 0,
                "message": (
                    "Insight scores describe reading scores, not whether "
                    "guidance helped. Collect client feedback or follow-up "
                    "outcomes to measure effectiveness."
                ),
            },

            "consultation_insights": consultation_insights,

            "data_quality": {
                "records_analyzed": len(safe_readings),
                "records_with_scores": len(scores),
                "records_with_timestamps": len(dated_readings),
            },
        }


consultant_analytics_service = ConsultantAnalyticsService()
