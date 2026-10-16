import io
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# MediaPipe import
# ---------------------------------------------------------------------------
try:
    import mediapipe as mp
    from mediapipe.python.solutions import hands as mp_hands
except (ImportError, AttributeError):
    try:
        import mediapipe.solutions.hands as mp_hands
        mp = None
    except (ImportError, AttributeError):
        mp = None
        mp_hands = None


class PalmAnalysisEngine:
    """
    Computer-vision based palm analysis engine.

    The engine performs:
        1. Image decoding and validation
        2. Hand landmark detection using MediaPipe
        3. Palm geometry extraction
        4. Palm ROI / crease analysis using OpenCV
        5. Palm structure classification
        6. Landmark-guided palm line candidate generation
        7. Confidence estimation

    Important:
        Palmistry interpretations are symbolic/application-level
        interpretations. The computer vision layer reports measurable
        image and hand-structure features.
    """

    def __init__(self):
        self.hands = None

        if mp_hands is not None:
            self.hands = mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    # -----------------------------------------------------------------------
    # Basic geometry
    # -----------------------------------------------------------------------

    @staticmethod
    def _calculate_distance(
        p1: Tuple[float, float],
        p2: Tuple[float, float],
    ) -> float:
        return float(
            np.linalg.norm(
                np.array(p1, dtype=np.float32)
                - np.array(p2, dtype=np.float32)
            )
        )

    @staticmethod
    def _calculate_angle(
        a: Tuple[float, float],
        b: Tuple[float, float],
        c: Tuple[float, float],
    ) -> float:
        """Return angle ABC in degrees."""
        ba = np.array(a, dtype=np.float32) - np.array(b, dtype=np.float32)
        bc = np.array(c, dtype=np.float32) - np.array(b, dtype=np.float32)

        denominator = (
            np.linalg.norm(ba) * np.linalg.norm(bc)
        )

        if denominator < 1e-7:
            return 0.0

        cosine_angle = np.dot(ba, bc) / denominator

        angle = np.arccos(
            np.clip(cosine_angle, -1.0, 1.0)
        )

        return float(np.degrees(angle))

    @staticmethod
    def _interpolate(
        p1: Dict[str, float],
        p2: Dict[str, float],
        factor: float,
    ) -> Dict[str, float]:
        """Linearly interpolate between normalized landmark points."""
        factor = float(np.clip(factor, 0.0, 1.0))

        return {
            "x": round(
                p1["x"] + (p2["x"] - p1["x"]) * factor,
                4,
            ),
            "y": round(
                p1["y"] + (p2["y"] - p1["y"]) * factor,
                4,
            ),
        }

    # -----------------------------------------------------------------------
    # Palm ROI
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_palm_roi(
        image: np.ndarray,
        pixel_landmarks: List[Tuple[int, int, float]],
    ) -> Tuple[np.ndarray, Dict[str, int]]:
        """
        Extract a palm-centered crop from detected hand landmarks.

        The crop is based on the wrist and MCP joints rather than a
        hard-coded image rectangle.
        """
        h, w = image.shape[:2]

        palm_points = np.array(
            [
                [pixel_landmarks[i][0], pixel_landmarks[i][1]]
                for i in [0, 5, 9, 13, 17]
            ],
            dtype=np.float32,
        )

        x_min = int(max(0, np.min(palm_points[:, 0]) - 35))
        x_max = int(min(w, np.max(palm_points[:, 0]) + 35))
        y_min = int(max(0, np.min(palm_points[:, 1]) - 35))
        y_max = int(min(h, np.max(palm_points[:, 1]) + 35))

        if x_max <= x_min or y_max <= y_min:
            return np.empty((0, 0, 3), dtype=np.uint8), {
                "x_min": x_min,
                "x_max": x_max,
                "y_min": y_min,
                "y_max": y_max,
            }

        crop = image[y_min:y_max, x_min:x_max]

        return crop, {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        }

    # -----------------------------------------------------------------------
    # Palm crease analysis
    # -----------------------------------------------------------------------

    @staticmethod
    def _analyze_creases(
        palm_crop: np.ndarray,
    ) -> Dict[str, Any]:
        """Extract image-derived crease evidence from the palm ROI.

        This is a classical computer-vision step. It does not train a model.
        Dark crease-like structures are enhanced with a black-hat transform and
        adaptive thresholding. The result is evidence for downstream scoring;
        it is not presented as medically or scientifically validated palm-line
        detection.
        """
        if palm_crop.size == 0:
            return {
                "edge_density": 0.0,
                "mean_intensity": 0.0,
                "contrast": 0.0,
                "crease_intensity": "Unknown",
                "crease_map_available": False,
                "crease_pixel_ratio": 0.0,
                "crease_map": None,
            }

        gray = cv2.cvtColor(palm_crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        edges = cv2.Canny(blurred, 40, 120)
        edge_density = float(np.count_nonzero(edges) / max(edges.size, 1))

        # Palm creases are commonly darker than nearby skin. Black-hat
        # morphology highlights dark structures while suppressing slow lighting
        # changes. A relatively large kernel is used because the ROI is palm-sized.
        kernel_size = max(15, int(round(min(gray.shape[:2]) * 0.07)))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        blackhat = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, kernel)

        # Keep stronger dark-crease responses. Adaptive thresholding helps with
        # uneven illumination across the palm.
        local_threshold = cv2.adaptiveThreshold(
            blackhat,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            -2,
        )
        clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        crease_map = cv2.morphologyEx(
            local_threshold, cv2.MORPH_OPEN, clean_kernel, iterations=1
        )
        crease_map = cv2.morphologyEx(
            crease_map, cv2.MORPH_CLOSE, clean_kernel, iterations=1
        )

        crease_pixel_ratio = float(
            np.count_nonzero(crease_map) / max(crease_map.size, 1)
        )
        mean_intensity = float(np.mean(enhanced))
        contrast = float(np.std(enhanced))

        if crease_pixel_ratio >= 0.08:
            intensity = "High"
        elif crease_pixel_ratio >= 0.025:
            intensity = "Moderate"
        else:
            intensity = "Low"

        return {
            "edge_density": round(edge_density, 4),
        "mean_intensity": round(mean_intensity, 2),
        "contrast": round(contrast, 2),
        "crease_intensity": intensity,
        "crease_map_available": True,
        "crease_pixel_ratio": round(crease_pixel_ratio, 4),
        "crease_map": crease_map,
        }

    @staticmethod
    def _sample_line_evidence(
        crease_map: Optional[np.ndarray],
        points: List[Dict[str, float]],
        band_radius: int = 7,
        samples_per_segment: int = 80,
    ) -> Dict[str, Any]:
        """Measure crease evidence around a landmark-guided trajectory.

        The trajectory supplies anatomical context; the score itself comes from
        the image-derived crease map. This avoids claiming that landmarks alone
        detected a palm crease.
        """
        if crease_map is None or crease_map.size == 0 or len(points) < 2:
            return {
                "clarity_score": None,
                "support_ratio": None,
                "mean_response": None,
                "samples": 0,
            }

        h, w = crease_map.shape[:2]
        values: List[float] = []

        for p1, p2 in zip(points[:-1], points[1:]):
            segment_length = max(
                2.0,
                float(
                    np.hypot(
                        (p2["x"] - p1["x"]) * w,
                        (p2["y"] - p1["y"]) * h,
                    )
                ),
            )
            count = max(10, int(samples_per_segment * segment_length / max(w, h)))

            for alpha in np.linspace(0.0, 1.0, count):
                x = int(round((p1["x"] + (p2["x"] - p1["x"]) * alpha) * (w - 1)))
                y = int(round((p1["y"] + (p2["y"] - p1["y"]) * alpha) * (h - 1)))
                x0 = max(0, x - band_radius)
                x1 = min(w, x + band_radius + 1)
                y0 = max(0, y - band_radius)
                y1 = min(h, y + band_radius + 1)
                patch = crease_map[y0:y1, x0:x1]
                if patch.size:
                    values.append(float(np.count_nonzero(patch)) / patch.size)

        if not values:
            return {
                "clarity_score": None,
                "support_ratio": None,
                "mean_response": None,
                "samples": 0,
            }

        mean_response = float(np.mean(values))
        support_ratio = float(np.mean(np.asarray(values) >= 0.08))
        # Convert image evidence to a bounded technical score.
        clarity_score = float(np.clip(
            0.55 * min(mean_response / 0.20, 1.0)
            + 0.45 * support_ratio,
            0.0,
            1.0,
        ))

        return {
            "clarity_score": round(clarity_score, 3),
            "support_ratio": round(support_ratio, 3),
            "mean_response": round(mean_response, 4),
            "samples": len(values),
        }

    # -----------------------------------------------------------------------
    # Landmark-guided line candidates
    # -----------------------------------------------------------------------


    @staticmethod
    def _analyze_line_characteristics(
        points: List[Dict[str, float]],
        image_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Derive geometric characteristics from a candidate trajectory.

        These are measurable trajectory characteristics, not claims that the
        actual palm crease has been segmented. Branching/intersections are
        therefore reported as unavailable until a true crease segmentation
        model or robust image-based topology detector is added.
        """
        if len(points) < 2:
            return {
                "length_normalized": 0.0,
                "curvature": 0.0,
                "curvature_level": "unavailable",
                "direction": "unavailable",
                "continuity_proxy": None,
                "branching": "unavailable",
                "intersections": "unavailable",
            }

        coords = np.array(
            [[float(p["x"]), float(p["y"])] for p in points],
            dtype=np.float32,
        )

        segment_lengths = np.linalg.norm(
            np.diff(coords, axis=0),
            axis=1,
        )
        total_length = float(np.sum(segment_lengths))

        angles: List[float] = []
        for i in range(1, len(coords) - 1):
            v1 = coords[i] - coords[i - 1]
            v2 = coords[i + 1] - coords[i]
            n1 = float(np.linalg.norm(v1))
            n2 = float(np.linalg.norm(v2))
            if n1 > 1e-7 and n2 > 1e-7:
                cosine = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
                angles.append(float(np.degrees(np.arccos(cosine))))

        mean_turn = float(np.mean(angles)) if angles else 0.0
        curvature = float(np.clip(mean_turn / 90.0, 0.0, 1.0))

        if curvature >= 0.55:
            curvature_level = "high"
        elif curvature >= 0.25:
            curvature_level = "moderate"
        else:
            curvature_level = "low"

        start = coords[0]
        end = coords[-1]
        dx = float(end[0] - start[0])
        dy = float(end[1] - start[1])

        if abs(dx) < 0.08 and abs(dy) < 0.08:
            direction = "short_displacement"
        elif abs(dy) >= abs(dx) * 1.5:
            direction = "vertical"
        elif abs(dx) >= abs(dy) * 1.5:
            direction = "horizontal"
        elif dx * dy < 0:
            direction = "diagonal_upward"
        else:
            direction = "diagonal_downward"

        clarity = image_evidence.get("clarity_score")
        support = image_evidence.get("support_ratio")
        if clarity is None or support is None:
            continuity_proxy = None
        else:
            continuity_proxy = round(
                float(np.clip(0.6 * float(clarity) + 0.4 * float(support), 0.0, 1.0)),
                3,
            )

        return {
            "length_normalized": round(total_length, 3),
            "curvature": round(curvature, 3),
            "curvature_level": curvature_level,
            "direction": direction,
            "continuity_proxy": continuity_proxy,
            "branching": "unavailable",
            "intersections": "unavailable",
        }

    @staticmethod
    def _line_characteristic_interpretation(
        line_name: str,
        characteristics: Dict[str, Any],
        evidence_level: str,
    ) -> str:
        """Generate traditional, non-predictive text from measurable features."""
        curvature_level = characteristics.get("curvature_level")
        direction = characteristics.get("direction")
        continuity = characteristics.get("continuity_proxy")

        if evidence_level == "limited":
            prefix = "The candidate trajectory has limited image evidence. "
        else:
            prefix = "Based on the candidate trajectory and image evidence, "

        continuity_text = ""
        if continuity is not None:
            if continuity >= 0.80:
                continuity_text = "the visual support is relatively continuous"
            elif continuity >= 0.55:
                continuity_text = "the visual support is moderately continuous"
            else:
                continuity_text = "the visual support is relatively weak or interrupted"

        curvature_text = {
            "low": "the trajectory is relatively straight",
            "moderate": "the trajectory shows moderate curvature",
            "high": "the trajectory shows pronounced curvature",
            "unavailable": "the trajectory curvature could not be estimated",
        }.get(curvature_level, "the trajectory curvature could not be estimated")

        line_theme = {
            "life": "vitality and life experience",
            "head": "thinking and reasoning tendencies",
            "heart": "emotional expression and relationships",
            "fate": "career direction and life-path themes",
            "sun": "creativity, recognition, and self-expression",
        }.get(line_name, "traditional palmistry themes")

        parts = [
            prefix,
            f"the line candidate associated with {line_theme} ",
            f"{curvature_text}",
        ]
        if direction != "unavailable":
            parts.append(f" and follows a {direction} overall direction")
        if continuity_text:
            parts.append(f"; {continuity_text}")
        parts.append(".")
        return "".join(parts)

    def _compute_palm_lines(
        self,
        landmarks: List[Dict[str, float]],
        crease_map: Optional[np.ndarray],
    ) -> Dict[str, Dict[str, Any]]:
        """Create anatomical trajectories and attach image-derived evidence.

        These remain candidate trajectories because the system has no trained
        palm-line segmentation model yet.
        """
        p0 = landmarks[0]   # Wrist
        p1 = landmarks[1]   # Thumb CMC
        p2 = landmarks[2]   # Thumb MCP
        p5 = landmarks[5]   # Index MCP
        p9 = landmarks[9]   # Middle MCP
        p13 = landmarks[13] # Ring MCP
        p14 = landmarks[14] # Ring PIP
        p16 = landmarks[16] # Ring DIP
        p17 = landmarks[17] # Pinky MCP

        life = [
            self._interpolate(p5, p2, 0.45),
            self._interpolate(p2, p1, 0.50),
            self._interpolate(p1, p0, 0.55),
            self._interpolate(p0, p1, 0.25),
        ]
        head = [
            self._interpolate(p5, p2, 0.35),
            self._interpolate(p9, p0, 0.48),
            self._interpolate(p17, p0, 0.42),
        ]
        heart = [
            self._interpolate(p17, p0, 0.28),
            self._interpolate(p13, p0, 0.36),
            self._interpolate(p5, p9, 0.50),
        ]
        fate = [
            self._interpolate(p0, p17, 0.30),
            self._interpolate(p9, p0, 0.52),
            self._interpolate(p9, p0, 0.22),
        ]
        sun = [
            self._interpolate(p0, p13, 0.25),
            self._interpolate(p9, p13, 0.55),
            self._interpolate(p13, p14, 0.65),
            self._interpolate(p14, p16, 0.55),
        ]

        candidates = {
            "life": life,
            "head": head,
            "heart": heart,
            "fate": fate,
            "sun": sun,
        }

        results: Dict[str, Dict[str, Any]] = {}
        for name, points in candidates.items():
            evidence = self._sample_line_evidence(crease_map, points)
            clarity = evidence.get("clarity_score")
            if clarity is None:
                evidence_level = "limited"
            elif clarity >= 0.75:
                evidence_level = "strong"
            elif clarity >= 0.50:
                evidence_level = "moderate"
            else:
                evidence_level = "limited"

            characteristics = self._analyze_line_characteristics(
                points,
                evidence,
            )
            results[name] = {
                "status": "candidate_trajectory",
                "detection_method": "landmark_guided_with_image_evidence",
                "coordinates": points,
                "image_evidence": evidence,
                "characteristics": characteristics,
                "characteristic_interpretation": (
                    self._line_characteristic_interpretation(
                        name,
                        characteristics,
                        evidence_level,
                    )
                ),
            }

        return results

    # -----------------------------------------------------------------------
    # Palm structure
    # -----------------------------------------------------------------------

    def _classify_hand_structure(
        self,
        pixel_landmarks: List[Tuple[int, int, float]],
    ) -> Dict[str, Any]:
        wrist = (
            pixel_landmarks[0][0],
            pixel_landmarks[0][1],
        )

        index_mcp = (
            pixel_landmarks[5][0],
            pixel_landmarks[5][1],
        )

        middle_mcp = (
            pixel_landmarks[9][0],
            pixel_landmarks[9][1],
        )

        middle_tip = (
            pixel_landmarks[12][0],
            pixel_landmarks[12][1],
        )

        pinky_mcp = (
            pixel_landmarks[17][0],
            pixel_landmarks[17][1],
        )

        palm_length = self._calculate_distance(
            wrist,
            middle_mcp,
        )

        palm_width = self._calculate_distance(
            index_mcp,
            pinky_mcp,
        )

        middle_finger_length = self._calculate_distance(
            middle_mcp,
            middle_tip,
        )

        palm_aspect_ratio = palm_length / max(
            palm_width,
            1e-5,
        )

        finger_to_palm_ratio = (
            middle_finger_length
            / max(palm_length, 1e-5)
        )

        is_palm_square = abs(
            palm_length - palm_width
        ) < (0.15 * max(palm_length, 1e-5))

        is_finger_long = (
            middle_finger_length
            > (0.80 * max(palm_length, 1e-5))
        )

        if is_palm_square and not is_finger_long:
            hand_element = (
                "Earth (Practical, Grounded, Realistic)"
            )
        elif is_palm_square and is_finger_long:
            hand_element = (
                "Air (Intellectual, Communicative, Analytical)"
            )
        elif not is_palm_square and not is_finger_long:
            hand_element = (
                "Fire (Passionate, Dynamic, Intuitive)"
            )
        else:
            hand_element = (
                "Water (Empathetic, Imaginative, Sensitive)"
            )

        return {
            "palm_length_px": round(palm_length, 2),
            "palm_width_px": round(palm_width, 2),
            "middle_finger_length_px": round(
                middle_finger_length,
                2,
            ),
            "palm_aspect_ratio": round(
                palm_aspect_ratio,
                3,
            ),
            "finger_to_palm_ratio": round(
                finger_to_palm_ratio,
                3,
            ),
            "is_palm_square": bool(is_palm_square),
            "is_finger_long": bool(is_finger_long),
            "element": hand_element,
        }

    # -----------------------------------------------------------------------
    # Mount analysis
    # -----------------------------------------------------------------------

    @staticmethod
    def _safe_patch(
        image: np.ndarray,
        center: Tuple[float, float],
        radius_x: float,
        radius_y: float,
    ) -> np.ndarray:
        """Return a bounded rectangular patch around a pixel-space center."""
        if image is None or image.size == 0:
            return np.empty((0, 0), dtype=np.uint8)

        h, w = image.shape[:2]
        cx, cy = center

        x0 = max(0, int(round(cx - radius_x)))
        x1 = min(w, int(round(cx + radius_x + 1)))
        y0 = max(0, int(round(cy - radius_y)))
        y1 = min(h, int(round(cy + radius_y + 1)))

        if x1 <= x0 or y1 <= y0:
            return np.empty((0, 0), dtype=np.uint8)

        patch = image[y0:y1, x0:x1]
        if patch.ndim == 3:
            patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

        return patch

    @staticmethod
    def _mount_visual_score(
        patch: np.ndarray,
        palm_gray: np.ndarray,
        crease_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """Estimate visual mount prominence from measurable 2-D image features.

        This is a visual proxy, not a measurement of physical elevation.
        No ML model or training is involved.
        """
        if (
            patch is None
            or patch.size == 0
            or palm_gray is None
            or palm_gray.size == 0
        ):
            return {
                "prominence_score": None,
                "confidence": 0.0,
                "local_contrast": None,
                "edge_density": None,
                "crease_density": None,
                "status": "insufficient_image_data",
            }

        patch_float = patch.astype(np.float32)
        palm_float = palm_gray.astype(np.float32)

        # Robust local-vs-global brightness difference.
        local_mean = float(np.mean(patch_float))
        global_mean = float(np.mean(palm_float))
        global_std = float(np.std(palm_float))
        local_contrast = abs(local_mean - global_mean) / max(global_std, 1.0)

        # Texture/shape evidence.
        edges = cv2.Canny(patch, 40, 120)
        edge_density = float(np.count_nonzero(edges) / max(edges.size, 1))

        crease_density = 0.0
        if crease_map is not None and crease_map.size:
            # Resize only for robust shape compatibility.
            local_map = cv2.resize(
                crease_map,
                (patch.shape[1], patch.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
            crease_density = float(
                np.count_nonzero(local_map) / max(local_map.size, 1)
            )

        # Scores are intentionally conservative: these quantify visual
        # prominence evidence rather than claiming anatomical elevation.
        contrast_score = float(np.clip(local_contrast / 2.0, 0.0, 1.0))
        edge_score = float(np.clip(edge_density / 0.12, 0.0, 1.0))
        crease_score = float(np.clip(crease_density / 0.20, 0.0, 1.0))

        prominence_score = float(
            np.clip(
                0.35 * contrast_score
                + 0.30 * edge_score
                + 0.35 * crease_score,
                0.0,
                1.0,
            )
        )

        # Confidence reflects patch quality, not palmistry truth.
        patch_size_score = float(
            np.clip(patch.size / 2500.0, 0.0, 1.0)
        )
        confidence = float(
            np.clip(
                0.55 * patch_size_score
                + 0.45 * min(global_std / 40.0, 1.0),
                0.0,
                1.0,
            )
        )

        if prominence_score >= 0.67:
            level = "high"
        elif prominence_score >= 0.34:
            level = "moderate"
        else:
            level = "low"

        return {
            "prominence_score": round(prominence_score, 3),
            "prominence_level": level,
            "confidence": round(confidence, 3),
            "local_contrast": round(local_contrast, 3),
            "edge_density": round(edge_density, 4),
            "crease_density": round(crease_density, 4),
            "status": "visual_proxy",
        }

    def _analyze_mounts(
        self,
        palm_crop: np.ndarray,
        roi: Dict[str, int],
        pixel_landmarks: List[Tuple[int, int, float]],
        crease_map: Optional[np.ndarray],
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze four requested mounts using landmark-relative image regions.

        Mount regions are approximate anatomical zones derived from hand
        landmarks. Their scores are visual 2-D proxies and should not be
        interpreted as physical measurements.
        """
        if palm_crop is None or palm_crop.size == 0:
            return {
                name: {
                    "name": label,
                    "significance": significance,
                    "prominence_score": None,
                    "prominence_level": "unavailable",
                    "confidence": 0.0,
                    "status": "insufficient_image_data",
                }
                for name, label, significance in [
                    (
                        "jupiter",
                        "Mount of Jupiter",
                        "Traditionally associated with ambition, leadership, and vision.",
                    ),
                    (
                        "saturn",
                        "Mount of Saturn",
                        "Traditionally associated with discipline, introspection, and depth.",
                    ),
                    (
                        "apollo",
                        "Mount of Sun (Apollo)",
                        "Traditionally associated with creativity and self-expression.",
                    ),
                    (
                        "venus",
                        "Mount of Venus",
                        "Traditionally associated with vitality, passion, and warmth.",
                    ),
                ]
            }

        x0 = roi["x_min"]
        y0 = roi["y_min"]

        def local_point(index: int) -> Tuple[float, float]:
            x, y, _ = pixel_landmarks[index]
            return float(x - x0), float(y - y0)

        p0 = local_point(0)
        p1 = local_point(1)
        p5 = local_point(5)
        p9 = local_point(9)
        p13 = local_point(13)
        p17 = local_point(17)

        palm_h, palm_w = palm_crop.shape[:2]
        palm_center = np.mean(
            np.array([p0, p5, p9, p13, p17], dtype=np.float32),
            axis=0,
        )

        # Mount centers are placed below the corresponding MCP region,
        # toward the interior of the palm. Venus is the thenar/thumb-side
        # region between the thumb base and wrist.
        jupiter_center = (
            0.65 * p5[0] + 0.35 * palm_center[0],
            0.65 * p5[1] + 0.35 * palm_center[1] + 0.12 * palm_h,
        )
        saturn_center = (
            0.70 * p9[0] + 0.30 * palm_center[0],
            0.70 * p9[1] + 0.30 * palm_center[1] + 0.10 * palm_h,
        )
        apollo_center = (
            0.70 * p13[0] + 0.30 * palm_center[0],
            0.70 * p13[1] + 0.30 * palm_center[1] + 0.10 * palm_h,
        )
        venus_center = (
            0.55 * p1[0] + 0.45 * p0[0] + 0.08 * palm_w,
            0.55 * p1[1] + 0.45 * p0[1] + 0.10 * palm_h,
        )

        radius_x = max(18.0, 0.16 * palm_w)
        radius_y = max(18.0, 0.14 * palm_h)

        mount_specs = {
            "jupiter": {
                "name": "Mount of Jupiter",
                "significance": "Traditionally associated with ambition, leadership, and vision.",
                "center": jupiter_center,
            },
            "saturn": {
                "name": "Mount of Saturn",
                "significance": "Traditionally associated with discipline, introspection, and depth.",
                "center": saturn_center,
            },
            "apollo": {
                "name": "Mount of Sun (Apollo)",
                "significance": "Traditionally associated with creativity and self-expression.",
                "center": apollo_center,
            },
            "venus": {
                "name": "Mount of Venus",
                "significance": "Traditionally associated with vitality, passion, and warmth.",
                "center": venus_center,
            },
        }

        results: Dict[str, Dict[str, Any]] = {}

        for name, spec in mount_specs.items():
            patch = self._safe_patch(
                palm_crop,
                spec["center"],
                radius_x,
                radius_y,
            )

            visual = self._mount_visual_score(
                patch=patch,
                palm_gray=cv2.cvtColor(palm_crop, cv2.COLOR_BGR2GRAY),
                crease_map=crease_map,
            )

            results[name] = {
                "name": spec["name"],
                "significance": spec["significance"],
                "region_center": {
                    "x": round(float(spec["center"][0]), 2),
                    "y": round(float(spec["center"][1]), 2),
                },
                **visual,
            }

        return results

    # -----------------------------------------------------------------------
    # Confidence
    # -----------------------------------------------------------------------

    @staticmethod
    def _calculate_analysis_confidence(
        landmarks_count: int,
        crease_metrics: Dict[str, Any],
        palm_structure: Dict[str, Any],
    ) -> float:
        """
        Estimate image-analysis confidence.

        This is a technical CV confidence estimate, NOT a claim about
        the truth of a palmistry interpretation.
        """
        landmark_score = min(
            landmarks_count / 21.0,
            1.0,
        )

        edge_density = float(
            crease_metrics.get("edge_density", 0.0)
        )

        # Extremely low edge density usually indicates poor visibility.
        # Very high density can indicate excessive noise/background texture.
        if 0.03 <= edge_density <= 0.15:
            crease_score = 1.0
        elif edge_density < 0.03:
            crease_score = edge_density / 0.03
        else:
            crease_score = max(
                0.0,
                1.0 - ((edge_density - 0.15) / 0.15),
            )

        aspect_ratio = float(
            palm_structure.get("palm_aspect_ratio", 0.0)
        )

        geometry_score = (
            1.0
            if 0.5 <= aspect_ratio <= 2.5
            else 0.5
        )

        confidence = (
            landmark_score * 0.50
            + crease_score * 0.30
            + geometry_score * 0.20
        )

        return round(
            float(np.clip(confidence, 0.0, 1.0)),
            2,
        )

    # -----------------------------------------------------------------------
    # Main processing
    # -----------------------------------------------------------------------

    def process_image(
        self,
        image_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Process an uploaded palm image.

        Returns a detected=False response when a real hand cannot
        be detected. No fabricated fallback analysis is returned.
        """

        if not image_bytes:
            raise ValueError(
                "The submitted image is empty."
            )

        nparr = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        img_bgr = cv2.imdecode(
            nparr,
            cv2.IMREAD_COLOR,
        )

        if img_bgr is None:
            raise ValueError(
                "Unable to decode the submitted image."
            )

        height, width = img_bgr.shape[:2]

        if height < 100 or width < 100:
            raise ValueError(
                "Image resolution is too small for palm analysis."
            )

        img_rgb = cv2.cvtColor(
            img_bgr,
            cv2.COLOR_BGR2RGB,
        )

        # ---------------------------------------------------------------
        # MediaPipe unavailable
        # ---------------------------------------------------------------
        if self.hands is None:
            return {
                "detected": False,
                "message": (
                    "Palm analysis is currently unavailable because "
                    "the hand-detection model is not installed correctly."
                ),
                "analysis_confidence": 0.0,
            }

        # ---------------------------------------------------------------
        # Hand detection
        # ---------------------------------------------------------------
        results = self.hands.process(img_rgb)

        if not results.multi_hand_landmarks:
            return {
                "detected": False,
                "message": (
                    "No hand detected. Please upload a clear image "
                    "of an open palm with good lighting."
                ),
                "analysis_confidence": 0.0,
            }

        hand_landmarks = results.multi_hand_landmarks[0]

        handedness = "Right"

        if results.multi_handedness:
            handedness = (
                results.multi_handedness[0]
                .classification[0]
                .label
            )

        # ---------------------------------------------------------------
        # Normalized landmarks
        # ---------------------------------------------------------------
        normalized_landmarks = [
            {
                "x": round(
                    float(landmark.x),
                    4,
                ),
                "y": round(
                    float(landmark.y),
                    4,
                ),
                "z": round(
                    float(landmark.z),
                    4,
                ),
            }
            for landmark in hand_landmarks.landmark
        ]

        # ---------------------------------------------------------------
        # Pixel landmarks
        # ---------------------------------------------------------------
        pixel_landmarks = [
            (
                int(np.clip(landmark.x * width, 0, width - 1)),
                int(np.clip(landmark.y * height, 0, height - 1)),
                float(landmark.z),
            )
            for landmark in hand_landmarks.landmark
        ]

        # ---------------------------------------------------------------
        # Palm structure
        # ---------------------------------------------------------------
        palm_structure = self._classify_hand_structure(
            pixel_landmarks
        )

        # ---------------------------------------------------------------
        # Palm ROI
        # ---------------------------------------------------------------
        palm_crop, roi = self._get_palm_roi(
            img_bgr,
            pixel_landmarks,
        )

        crease_metrics = self._analyze_creases(
            palm_crop
        )

        # ---------------------------------------------------------------
        # Landmark-guided line candidates
        # ---------------------------------------------------------------
        line_analysis = self._compute_palm_lines(
            normalized_landmarks,
            crease_metrics.get("crease_map"),
        )

        # ---------------------------------------------------------------
        # Mount analysis
        # ---------------------------------------------------------------
        mount_analysis = self._analyze_mounts(
            palm_crop=palm_crop,
            roi=roi,
            pixel_landmarks=pixel_landmarks,
            crease_map=crease_metrics.get("crease_map"),
        )

        # ---------------------------------------------------------------
        # Structured palmistry interpretation
        # ---------------------------------------------------------------
        interpretation = self._build_interpretation(
            palm_structure=palm_structure,
            line_analysis=line_analysis,
            mount_analysis=mount_analysis,
        )

        # ---------------------------------------------------------------
        # Technical analysis confidence
        # ---------------------------------------------------------------
        analysis_confidence = (
            self._calculate_analysis_confidence(
                landmarks_count=len(pixel_landmarks),
                crease_metrics=crease_metrics,
                palm_structure=palm_structure,
            )
        )

        return self._format_results(
            handedness=handedness,
            palm_structure=palm_structure,
            crease_metrics=crease_metrics,
            analysis_confidence=analysis_confidence,
            landmarks=normalized_landmarks,
            line_analysis=line_analysis,
            mount_analysis=mount_analysis,
            roi=roi,
            interpretation=interpretation,
        )

    # -----------------------------------------------------------------------
    # Palmistry interpretation
    # -----------------------------------------------------------------------

    @staticmethod
    def _evidence_level(score: Optional[float]) -> str:
        """Translate a technical image-evidence score into a cautious label."""
        if score is None:
            return "unavailable"
        if score >= 0.75:
            return "strong"
        if score >= 0.50:
            return "moderate"
        return "limited"

    @classmethod
    def _interpret_line(
        cls,
        line_name: str,
        line_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert measured line evidence into structured traditional palmistry
        language.

        This layer does not claim that the CV pipeline has scientifically
        identified a palm line. It interprets the candidate trajectory only
        when image evidence is available.
        """
        evidence = line_data.get("image_evidence") or {}
        clarity = evidence.get("clarity_score")
        support = evidence.get("support_ratio")

        evidence_level = cls._evidence_level(clarity)

        if clarity is None:
            quality = "unavailable"
        elif clarity >= 0.75:
            quality = "clear_candidate"
        elif clarity >= 0.50:
            quality = "moderate_candidate"
        else:
            quality = "weak_candidate"

        interpretations = {
            "life": {
                "theme": "vitality, resilience, and life experience",
                "strong": (
                    "Traditionally interpreted as a clearer indication of "
                    "vitality, resilience, and engagement with life experiences."
                ),
                "moderate": (
                    "Traditionally interpreted as a moderate indication of "
                    "vitality and resilience, with the overall reading "
                    "depending on other palm features."
                ),
                "limited": (
                    "The candidate trajectory has limited image support, so "
                    "no strong traditional interpretation should be assigned."
                ),
            },
            "head": {
                "theme": "thinking, reasoning, and mental tendencies",
                "strong": (
                    "Traditionally interpreted as a clearer indication of "
                    "thinking style, reasoning, and mental tendencies."
                ),
                "moderate": (
                    "Traditionally interpreted as a moderate indication of "
                    "thinking and reasoning tendencies."
                ),
                "limited": (
                    "The candidate trajectory has limited image support, so "
                    "mental-style interpretation should remain tentative."
                ),
            },
            "heart": {
                "theme": "emotions, attachment, and relationships",
                "strong": (
                    "Traditionally interpreted as a clearer indication of "
                    "emotional expression and relationship tendencies."
                ),
                "moderate": (
                    "Traditionally interpreted as a moderate indication of "
                    "emotional and relationship tendencies."
                ),
                "limited": (
                    "The candidate trajectory has limited image support, so "
                    "relationship interpretation should remain tentative."
                ),
            },
            "fate": {
                "theme": "career direction and life-path themes",
                "strong": (
                    "Traditionally interpreted as a clearer indication of "
                    "career direction, responsibility, and life-path themes."
                ),
                "moderate": (
                    "Traditionally interpreted as a moderate indication of "
                    "career and life-direction themes."
                ),
                "limited": (
                    "The candidate trajectory has limited image support, so "
                    "career interpretation should remain tentative."
                ),
            },
            "sun": {
                "theme": "creativity, recognition, and self-expression",
                "strong": (
                    "Traditionally interpreted as a clearer indication of "
                    "creative expression, recognition, and personal visibility."
                ),
                "moderate": (
                    "Traditionally interpreted as a moderate indication of "
                    "creativity, self-expression, and recognition themes."
                ),
                "limited": (
                    "The candidate trajectory has limited image support, so "
                    "recognition and creativity interpretation should remain tentative."
                ),
            },
        }

        spec = interpretations.get(line_name, {
            "theme": "a traditional palmistry theme",
            "strong": "The candidate shows relatively strong image support.",
            "moderate": "The candidate shows moderate image support.",
            "limited": "The candidate shows limited image support.",
        })

        if evidence_level == "strong":
            interpretation = spec["strong"]
        elif evidence_level == "moderate":
            interpretation = spec["moderate"]
        elif evidence_level == "limited":
            interpretation = spec["limited"]
        else:
            interpretation = (
                "No image-supported interpretation is available for this "
                "candidate trajectory."
            )

        return {
            "theme": spec["theme"],
            "evidence_level": evidence_level,
            "candidate_quality": quality,
            "interpretation": interpretation,
            "technical_basis": {
                "clarity_score": clarity,
                "support_ratio": support,
                "detection_status": line_data.get("status"),
                "detection_method": line_data.get("detection_method"),
            },
        }

    @staticmethod
    def _interpret_hand_type(palm_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Return structured traditional symbolism for the detected hand type."""
        element = str(palm_structure.get("element", "Unknown"))
        descriptions = {
            "Earth (Practical, Grounded, Realistic)": (
                "Traditionally associated with practicality, steadiness, "
                "grounded thinking, and a preference for tangible results."
            ),
            "Air (Intellectual, Communicative, Analytical)": (
                "Traditionally associated with intellectual curiosity, "
                "communication, analysis, and mental activity."
            ),
            "Fire (Passionate, Dynamic, Intuitive)": (
                "Traditionally associated with initiative, energy, "
                "confidence, passion, and dynamic expression."
            ),
            "Water (Empathetic, Imaginative, Sensitive)": (
                "Traditionally associated with empathy, imagination, "
                "sensitivity, intuition, and emotional awareness."
            ),
        }

        return {
            "element": element,
            "interpretation": descriptions.get(
                element,
                "The hand type could not be assigned a traditional interpretation."
            ),
            "basis": {
                "palm_aspect_ratio": palm_structure.get("palm_aspect_ratio"),
                "finger_to_palm_ratio": palm_structure.get("finger_to_palm_ratio"),
                "is_palm_square": palm_structure.get("is_palm_square"),
                "is_finger_long": palm_structure.get("is_finger_long"),
            },
        }

    @classmethod
    def _interpret_mounts(
        cls,
        mount_analysis: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Convert visual mount proxies into cautious traditional interpretations."""
        themes = {
            "jupiter": (
                "ambition, leadership, confidence, and vision",
                "Traditionally associated with ambition, leadership, confidence, and vision."
            ),
            "saturn": (
                "discipline, introspection, responsibility, and depth",
                "Traditionally associated with discipline, introspection, responsibility, and depth."
            ),
            "apollo": (
                "creativity, recognition, aesthetics, and self-expression",
                "Traditionally associated with creativity, recognition, aesthetics, and self-expression."
            ),
            "venus": (
                "vitality, warmth, affection, passion, and social energy",
                "Traditionally associated with vitality, warmth, affection, passion, and social energy."
            ),
        }

        interpreted: Dict[str, Dict[str, Any]] = {}

        for name, data in mount_analysis.items():
            prominence = data.get("prominence_score")
            confidence = data.get("confidence")
            level = data.get("prominence_level", "unavailable")
            theme, traditional_text = themes.get(
                name,
                ("a traditional palmistry theme", data.get("significance", "")),
            )

            if prominence is None:
                interpretation = (
                    "There is insufficient image data to provide a mount interpretation."
                )
            elif level == "high":
                interpretation = (
                    f"The visual proxy is relatively prominent. {traditional_text}"
                )
            elif level == "moderate":
                interpretation = (
                    f"The visual proxy is moderately prominent. {traditional_text}"
                )
            else:
                interpretation = (
                    f"The visual proxy is relatively subtle. {traditional_text}"
                )

            interpreted[name] = {
                "theme": theme,
                "prominence_level": level,
                "interpretation": interpretation,
                "technical_basis": {
                    "prominence_score": prominence,
                    "confidence": confidence,
                    "status": data.get("status"),
                },
            }

        return interpreted

    @classmethod
    def _build_interpretation(
        cls,
        palm_structure: Dict[str, Any],
        line_analysis: Dict[str, Dict[str, Any]],
        mount_analysis: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the structured palmistry interpretation layer.

        The result separates traditional symbolism from technical CV evidence.
        It is intentionally deterministic and does not train or call an ML model.
        """
        lines = {
            name: cls._interpret_line(name, data)
            for name, data in line_analysis.items()
        }

        return {
            "disclaimer": (
                "Palmistry interpretations are traditional/symbolic and are "
                "not scientific predictions or medical, financial, or other "
                "professional advice."
            ),
            "hand_type": cls._interpret_hand_type(palm_structure),
            "major_lines": lines,
            "mounts": cls._interpret_mounts(mount_analysis),
        }


    # -----------------------------------------------------------------------
    # Result formatting
    # -----------------------------------------------------------------------

    @staticmethod
    def _format_results(
        handedness: str,
        palm_structure: Dict[str, Any],
        crease_metrics: Dict[str, Any],
        analysis_confidence: float,
        landmarks: List[Dict[str, float]],
        line_analysis: Dict[str, Dict[str, Any]],
        mount_analysis: Dict[str, Dict[str, Any]],
        roi: Dict[str, int],
        interpretation: Dict[str, Any],
    ) -> Dict[str, Any]:

        element = palm_structure.get(
            "element",
            "Unknown",
        )

        # Attach measurable line characteristics to the structured
        # interpretation without changing the existing interpretation schema.
        for line_name, interpretation_key in (
            ("life", "life"),
            ("head", "head"),
            ("heart", "heart"),
            ("fate", "fate"),
            ("sun", "sun"),
        ):
            interpretation["major_lines"][interpretation_key]["characteristics"] = (
                line_analysis[line_name].get("characteristics", {})
            )
            interpretation["major_lines"][interpretation_key][
                "characteristic_interpretation"
            ] = line_analysis[line_name].get(
                "characteristic_interpretation",
                "",
            )

        return {
            "detected": True,

            "analysis_confidence": analysis_confidence,

            "landmarks_count": len(landmarks),

            "landmarks": landmarks,

            "image_analysis": {
                "roi": roi,
                "edge_density": crease_metrics.get(
                    "edge_density",
                    0.0,
                ),
                "mean_intensity": crease_metrics.get(
                    "mean_intensity",
                    0.0,
                ),
                "contrast": crease_metrics.get(
                    "contrast",
                    0.0,
                ),
                "crease_intensity": crease_metrics.get(
                    "crease_intensity",
                    "Unknown",
                ),
                "crease_pixel_ratio": crease_metrics.get(
                    "crease_pixel_ratio",
                    0.0,
                ),
            },

            "features": {
                "hand_type": {
                    "element": element,
                    "handedness": handedness,
                    "palm_aspect_ratio": palm_structure.get(
                        "palm_aspect_ratio"
                    ),
                    "finger_to_palm_ratio": palm_structure.get(
                        "finger_to_palm_ratio"
                    ),
                    "palm_length_px": palm_structure.get(
                        "palm_length_px"
                    ),
                    "palm_width_px": palm_structure.get(
                        "palm_width_px"
                    ),
                },

                "palm_structure": {
                    "is_palm_square": palm_structure.get(
                        "is_palm_square"
                    ),
                    "is_finger_long": palm_structure.get(
                        "is_finger_long"
                    ),
                    "middle_finger_length_px": palm_structure.get(
                        "middle_finger_length_px"
                    ),
                },

                "major_lines": {
                    "life_line": {
                        **line_analysis["life"],
                        "insight": (
                            "Palmistry interpretation: traditionally associated with vitality, resilience, and life experience."
                        ),
                    },
                    "head_line": {
                        **line_analysis["head"],
                        "insight": (
                            "Palmistry interpretation: traditionally associated with thinking, reasoning, and mental tendencies."
                        ),
                    },
                    "heart_line": {
                        **line_analysis["heart"],
                        "insight": (
                            "Palmistry interpretation: traditionally associated with emotions and relationships."
                        ),
                    },
                    "fate_line": {
                        **line_analysis["fate"],
                        "insight": (
                            "Palmistry interpretation: traditionally associated with career direction and life-path themes."
                        ),
                    },
                    "sun_line": {
                        **line_analysis["sun"],
                        "insight": (
                            "Palmistry interpretation: traditionally associated with creativity, recognition, and self-expression."
                        ),
                    },
                },

                "mounts": mount_analysis,

                "interpretation": interpretation,

                "line_coordinates": {
                    name: data["coordinates"]
                    for name, data in line_analysis.items()
                },
                "line_evidence": {
                    name: data["image_evidence"]
                    for name, data in line_analysis.items()
                },
            },
        }


# ---------------------------------------------------------------------------
# Global engine instance
# ---------------------------------------------------------------------------

palm_engine = PalmAnalysisEngine()