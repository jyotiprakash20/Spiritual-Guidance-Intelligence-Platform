"""
Palmistry interpretation rules.

This module consumes the structured output produced by palm_service.py and
converts measurable CV features into traditional/symbolic palmistry language.

Important:
- This is a rule-based interpretation layer.
- It does not train or run an ML model.
- It does not claim scientific prediction or physical measurement of mounts.
"""

from typing import Any, Dict, Optional


DISCLAIMER = (
    "Palmistry interpretations are traditional/symbolic and are not scientific "
    "predictions or medical, financial, or other professional advice."
)


class PalmInterpretationEngine:
    """Generate structured, deterministic palmistry interpretations."""

    def __init__(self) -> None:
        self.line_rules = {
            "life": {
                "theme": "vitality, resilience, and life experience",
                "clear": "Traditionally associated with vitality, resilience, and engagement with life experiences.",
                "limited": "The available image evidence is limited, so only a cautious traditional interpretation is provided.",
            },
            "head": {
                "theme": "thinking, reasoning, and mental tendencies",
                "clear": "Traditionally associated with thinking style, reasoning, and mental tendencies.",
                "limited": "The available image evidence is limited, so only a cautious traditional interpretation is provided.",
            },
            "heart": {
                "theme": "emotions, attachment, and relationships",
                "clear": "Traditionally associated with emotional expression, attachment, and relationship tendencies.",
                "limited": "The available image evidence is limited, so only a cautious traditional interpretation is provided.",
            },
            "fate": {
                "theme": "career direction and life-path themes",
                "clear": "Traditionally associated with career direction, responsibility, and life-path themes.",
                "limited": "The available image evidence is limited, so only a cautious traditional interpretation is provided.",
            },
            "sun": {
                "theme": "creativity, recognition, and self-expression",
                "clear": "Traditionally associated with creative expression, recognition, and personal visibility.",
                "limited": "The available image evidence is limited, so only a cautious traditional interpretation is provided.",
            },
        }

    @staticmethod
    def _evidence_level(clarity: Optional[float]) -> str:
        if clarity is None:
            return "unavailable"
        if clarity >= 0.75:
            return "strong"
        if clarity >= 0.50:
            return "moderate"
        return "limited"

    @staticmethod
    def _quality(level: str) -> str:
        return {
            "strong": "clear_candidate",
            "moderate": "usable_candidate",
            "limited": "weak_candidate",
            "unavailable": "not_available",
        }[level]

    @staticmethod
    def _characteristics(data: Dict[str, Any]) -> Dict[str, Any]:
        characteristics = data.get("characteristics")
        return characteristics if isinstance(characteristics, dict) else {}

    def _interpret_line(
        self,
        name: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        rule = self.line_rules[name]
        evidence = data.get("image_evidence") or {}
        clarity = evidence.get("clarity_score")
        level = self._evidence_level(clarity)
        characteristics = self._characteristics(data)

        interpretation = (
            rule["clear"] if level in {"strong", "moderate"} else rule["limited"]
        )

        # Add only characteristics that are actually supplied by the CV layer.
        additions = []

        length_category = characteristics.get("length_category")
        if length_category:
            additions.append(
                f"The candidate trajectory is classified as {length_category} in length."
            )

        curvature = characteristics.get("curvature_category")
        if curvature:
            additions.append(
                f"Its measured curvature is classified as {curvature}."
            )

        continuity = characteristics.get("continuity_category")
        if continuity:
            additions.append(
                f"The image-based continuity proxy is {continuity}."
            )

        if additions:
            interpretation += " " + " ".join(additions)

        return {
            "theme": rule["theme"],
            "evidence_level": level,
            "candidate_quality": self._quality(level),
            "interpretation": interpretation,
            "technical_basis": {
                "clarity_score": clarity,
                "support_ratio": evidence.get("support_ratio"),
                "mean_response": evidence.get("mean_response"),
                "detection_status": data.get("status"),
                "detection_method": data.get("detection_method"),
                "characteristics": characteristics,
            },
        }

    @staticmethod
    def _interpret_hand_type(hand_type: Dict[str, Any]) -> Dict[str, Any]:
        element = str(hand_type.get("element", "Unknown"))
        interpretations = {
            "Earth": "Traditionally associated with practicality, groundedness, stability, and realism.",
            "Air": "Traditionally associated with communication, analytical thinking, curiosity, and intellectual activity.",
            "Fire": "Traditionally associated with energy, initiative, confidence, passion, and dynamic expression.",
            "Water": "Traditionally associated with empathy, imagination, sensitivity, intuition, and emotional awareness.",
        }

        key = element.split(" ", 1)[0]
        return {
            "element": element,
            "interpretation": interpretations.get(
                key,
                "A traditional hand-type interpretation is unavailable for this classification.",
            ),
            "basis": {
                "palm_aspect_ratio": hand_type.get("palm_aspect_ratio"),
                "finger_to_palm_ratio": hand_type.get("finger_to_palm_ratio"),
                "is_palm_square": hand_type.get("is_palm_square"),
                "is_finger_long": hand_type.get("is_finger_long"),
            },
        }

    @staticmethod
    def _interpret_mount(
        name: str,
        mount: Dict[str, Any],
    ) -> Dict[str, Any]:
        themes = {
            "jupiter": "ambition, leadership, confidence, and vision",
            "saturn": "discipline, introspection, responsibility, and depth",
            "apollo": "creativity, recognition, aesthetics, and self-expression",
            "venus": "vitality, warmth, affection, passion, and social energy",
        }

        level = mount.get("prominence_level", "unavailable")
        if level == "high":
            wording = "The visual proxy is relatively prominent."
        elif level == "moderate":
            wording = "The visual proxy is moderately prominent."
        elif level == "low":
            wording = "The visual proxy is relatively subtle."
        else:
            wording = "The visual proxy could not be assessed reliably."

        return {
            "theme": themes.get(name, "traditional mount symbolism"),
            "prominence_level": level,
            "interpretation": (
                f"{wording} Traditionally associated with "
                f"{themes.get(name, 'traditional mount symbolism')}."
            ),
            "technical_basis": {
                "prominence_score": mount.get("prominence_score"),
                "confidence": mount.get("confidence"),
                "status": mount.get("status"),
            },
        }

    def interpret(self, palm_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert palm_service.py features into a structured interpretation.

        Expected input:
            result["features"]

        Note:
            Palm service stores some geometry flags in ``palm_structure``,
            while ratios and the element classification are stored in
            ``hand_type``. Both are combined here.
        """
        if not isinstance(palm_features, dict):
            raise ValueError("Palm features must be a dictionary.")

        hand_type = palm_features.get("hand_type") or {}
        palm_structure = palm_features.get("palm_structure") or {}

        # Merge the geometry flags from palm_structure into the hand-type
        # interpretation without changing the original CV feature structure.
        hand_type_for_interpretation = {
            **hand_type,
            "is_palm_square": palm_structure.get("is_palm_square"),
            "is_finger_long": palm_structure.get("is_finger_long"),
        }

        major_lines = palm_features.get("major_lines") or {}
        mounts = palm_features.get("mounts") or {}

        line_interpretations = {}
        for name in self.line_rules:
            source = major_lines.get(f"{name}_line")
            if source is None:
                source = major_lines.get(name)
            if isinstance(source, dict):
                line_interpretations[name] = self._interpret_line(name, source)
            else:
                line_interpretations[name] = {
                    "theme": self.line_rules[name]["theme"],
                    "evidence_level": "unavailable",
                    "candidate_quality": "not_available",
                    "interpretation": "No usable candidate data was supplied.",
                    "technical_basis": {},
                }

        mount_interpretations = {}
        for name in ("jupiter", "saturn", "apollo", "venus"):
            mount = mounts.get(name)
            if isinstance(mount, dict):
                mount_interpretations[name] = self._interpret_mount(name, mount)

        return {
            "disclaimer": DISCLAIMER,
            "hand_type": self._interpret_hand_type(hand_type_for_interpretation),
            "major_lines": line_interpretations,
            "mounts": mount_interpretations,
        }


palm_interpretation_engine = PalmInterpretationEngine()
