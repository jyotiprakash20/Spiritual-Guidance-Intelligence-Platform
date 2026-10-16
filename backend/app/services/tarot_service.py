import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class TarotReadingEngine:
    """
    Rule-based Tarot drawing engine.

    This service is responsible for:
    - loading the Tarot catalog
    - validating supported spreads
    - drawing unique cards randomly
    - accepting user-selected cards
    - assigning upright/reversed orientation
    - returning card metadata and meanings

    It does not use ML or model training.
    """

    SPREAD_CONFIGS: Dict[str, List[str]] = {
        "single": [
            "Insight / Focus",
        ],
        "three_card": [
            "Past Influences",
            "Present Momentum",
            "Emerging Outcome",
        ],
        "relationship": [
            "Your Stance",
            "Their Stance",
            "Shared Bond",
            "Direction",
        ],
        "career": [
            "Vocation",
            "Opportunity",
            "Challenge",
            "Strategy",
            "Achievement",
        ],
        "celtic_cross": [
            "Present Situation",
            "Challenge / Crossing Energy",
            "Foundation",
            "Recent Past",
            "Possible Future",
            "Higher Guidance",
            "Near Future",
            "External Influences",
            "Hopes and Fears",
            "Potential Outcome",
        ],
        "life_path": [
            "Current Life Energy",
            "Life Lesson",
            "Past Influence",
            "Present Challenge",
            "Opportunity",
            "Guidance",
            "Life Direction",
        ],
        # Backward-compatible legacy spreads.
        "cross": [
            "Core Self",
            "Underlying Challenge",
            "Foundation",
            "Near Future",
            "Spiritual Outcome",
        ],
        "horseshoe": [
            "Past Foundation",
            "Active Situation",
            "Hidden Factors",
            "Active Hurdle",
            "Surrounding Energies",
            "Recommended Action",
            "Culmination",
        ],
    }

    def __init__(self, catalog_path: str):
        self.catalog_path = str(catalog_path)
        self.deck = self._load_catalog(self.catalog_path)

        if len(self._unique_draw_pool()) != 78:
            raise ValueError(
                f"Tarot catalog must contain exactly 78 unique cards. "
                f"Found {len(self._unique_draw_pool())}."
            )

    # ------------------------------------------------------------------
    # CATALOG
    # ------------------------------------------------------------------

    @staticmethod
    def _load_catalog(catalog_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(catalog_path):
            raise FileNotFoundError(
                f"Tarot catalog not found at {catalog_path}"
            )

        with open(catalog_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Accept either:
        # [
        #   {...},
        #   {...}
        # ]
        #
        # or:
        #
        # {
        #   "cards": [...]
        # }
        if isinstance(data, dict):
            data = data.get("cards")

        if not isinstance(data, list) or not data:
            raise ValueError(
                "Tarot catalog must contain a non-empty list of cards."
            )

        valid_cards: List[Dict[str, Any]] = []

        for card in data:
            if not isinstance(card, dict):
                continue

            name = str(card.get("name", "")).strip()

            if not name:
                continue

            valid_cards.append(card)

        if not valid_cards:
            raise ValueError(
                "Tarot catalog contains no valid card records."
            )

        return valid_cards

    # ------------------------------------------------------------------
    # CARD IDENTITY
    # ------------------------------------------------------------------

    @staticmethod
    def _card_identity(card: Dict[str, Any]) -> str:
        """
        Build a stable identity for a Tarot card.

        Preference:
        1. id
        2. card_id
        3. uuid
        4. image_file
        5. name + value
        """

        for key in ("id", "card_id", "uuid"):
            value = card.get(key)

            if value is not None and str(value).strip():
                return f"{key}:{str(value).strip().lower()}"

        image_file = str(
            card.get("image_file", "")
        ).strip().lower()

        if image_file:
            return f"image:{image_file}"

        name = str(
            card.get("name", "")
        ).strip().lower()

        value = str(
            card.get("value", "")
        ).strip().lower()

        return f"card:{name}:{value}"

    def _unique_draw_pool(self) -> List[Dict[str, Any]]:
        """
        Remove duplicate catalog records.

        The project uses a 78-card Tarot deck, so this should result
        in exactly 78 unique cards.
        """

        unique_cards: List[Dict[str, Any]] = []
        seen = set()

        for card in self.deck:
            identity = self._card_identity(card)

            if identity in seen:
                continue

            seen.add(identity)
            unique_cards.append(card)

        return unique_cards

    # ------------------------------------------------------------------
    # SPREADS
    # ------------------------------------------------------------------

    @classmethod
    def _get_positions(
        cls,
        spread_type: str,
    ) -> List[str]:

        normalized = str(
            spread_type or ""
        ).strip().lower()

        if normalized not in cls.SPREAD_CONFIGS:
            supported = ", ".join(
                cls.SPREAD_CONFIGS.keys()
            )

            raise ValueError(
                f"Unsupported spread_type '{spread_type}'. "
                f"Supported spreads: {supported}"
            )

        return cls.SPREAD_CONFIGS[normalized]

    # ------------------------------------------------------------------
    # CARD LOOKUP
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_card_ids(
        card_data: Dict[str, Any],
    ) -> List[str]:
        """
        Return all useful identifiers for a catalog card.

        This allows the frontend to send either the catalog `id`,
        `card_id`, or `uuid` if needed.
        """

        identifiers: List[str] = []

        for key in ("id", "card_id", "uuid"):
            value = card_data.get(key)

            if value is not None:
                value = str(value).strip()

                if value:
                    identifiers.append(value)

        return identifiers

    def _find_card_by_id(
        self,
        card_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a card in the 78-card catalog using its stable ID.

        The frontend should normally send the catalog `id`.
        """

        requested_id = str(
            card_id
        ).strip().lower()

        if not requested_id:
            return None

        for card in self._unique_draw_pool():

            for candidate in self._candidate_card_ids(card):

                if candidate.lower() == requested_id:
                    return card

        return None

    # ------------------------------------------------------------------
    # CARD MEANINGS
    # ------------------------------------------------------------------

    @staticmethod
    def _meaning_for_orientation(
        card_data: Dict[str, Any],
        is_reversed: bool,
        orientation: str,
    ) -> str:

        if is_reversed:
            meaning = (
                card_data.get("meaning_reversed")
                or card_data.get("reversed_meaning")
            )
        else:
            meaning = (
                card_data.get("meaning_upright")
                or card_data.get("upright_meaning")
            )

        if meaning:
            return str(meaning)

        name = str(
            card_data.get(
                "name",
                "Unknown Card",
            )
        )

        return (
            f"{name} in "
            f"{orientation.lower()} alignment."
        )

    @staticmethod
    def _card_value(
        card_data: Dict[str, Any],
    ) -> Any:

        for key in (
            "value",
            "number",
            "archetype_number",
        ):
            if card_data.get(key) is not None:
                return card_data.get(key)

        return 0

    @staticmethod
    def _image_file(
        card_data: Dict[str, Any],
    ) -> str:

        image_file = card_data.get(
            "image_file"
        )

        if image_file:
            return str(image_file)

        return ""

    # ------------------------------------------------------------------
    # RESULT BUILDER
    # ------------------------------------------------------------------

    def _build_card_result(
        self,
        position: str,
        card_data: Dict[str, Any],
        reversed_probability: float,
    ) -> Dict[str, Any]:

        is_reversed = (
            random.random()
            < reversed_probability
        )

        orientation = (
            "Reversed"
            if is_reversed
            else "Upright"
        )

        card_id = None

        for key in (
            "id",
            "card_id",
            "uuid",
        ):
            value = card_data.get(key)

            if value is not None:
                value = str(value).strip()

                if value:
                    card_id = value
                    break

        return {
            "position": position,
            "card_id": card_id,
            "card_name": str(
                card_data.get(
                    "name",
                    "Unknown Card",
                )
            ),
            "orientation": orientation,
            "archetype_number": self._card_value(
                card_data
            ),
            "image_file": self._image_file(
                card_data
            ),
            "interpretation": self._meaning_for_orientation(
                card_data,
                is_reversed,
                orientation,
            ),
        }

    # ------------------------------------------------------------------
    # RANDOM DRAW
    # ------------------------------------------------------------------

    def draw_spread(
        self,
        spread_type: str = "three_card",
        reversed_probability: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Randomly draw a unique Tarot spread.

        This method is retained for backward compatibility.

        The new user-selection workflow should use
        `draw_selected_cards()`.
        """

        if not 0.0 <= reversed_probability <= 1.0:
            raise ValueError(
                "reversed_probability must be between "
                "0.0 and 1.0."
            )

        positions = self._get_positions(
            spread_type
        )

        draw_pool = self._unique_draw_pool()

        if len(draw_pool) < len(positions):
            raise ValueError(
                f"Tarot catalog has only "
                f"{len(draw_pool)} unique cards, "
                f"but the '{spread_type}' spread "
                f"requires {len(positions)}."
            )

        drawn_cards = random.sample(
            draw_pool,
            len(positions),
        )

        cards_drawn: List[Dict[str, Any]] = []

        for position, card_data in zip(
            positions,
            drawn_cards,
        ):
            cards_drawn.append(
                self._build_card_result(
                    position=position,
                    card_data=card_data,
                    reversed_probability=reversed_probability,
                )
            )

        return {
            "spread_type": str(
                spread_type
            ).strip().lower(),
            "card_count": len(cards_drawn),
            "cards": cards_drawn,
            "selection_mode": "random",
        }

    # ------------------------------------------------------------------
    # USER SELECTED DRAW
    # ------------------------------------------------------------------

    def draw_selected_cards(
        self,
        spread_type: str,
        selected_card_ids: Sequence[str],
        reversed_probability: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Process cards selected manually by the user.

        Expected flow:

            78 face-down cards
                    ↓
                shuffle
                    ↓
             user selects cards
                    ↓
             selected_card_ids
                    ↓
              reveal cards
                    ↓
        draw_selected_cards()

        The backend does NOT randomly choose different cards.

        It only:
        - validates the selected cards
        - assigns spread positions
        - determines orientation
        - returns card meanings
        """

        if not 0.0 <= reversed_probability <= 1.0:
            raise ValueError(
                "reversed_probability must be between "
                "0.0 and 1.0."
            )

        positions = self._get_positions(
            spread_type
        )

        if selected_card_ids is None:
            raise ValueError(
                "selected_card_ids is required."
            )

        selected_ids = [
            str(card_id).strip()
            for card_id in selected_card_ids
            if str(card_id).strip()
        ]

        required_count = len(positions)

        # --------------------------------------------------------------
        # Exact card count
        # --------------------------------------------------------------

        if len(selected_ids) != required_count:
            raise ValueError(
                f"The '{spread_type}' spread requires "
                f"{required_count} card"
                f"{'s' if required_count != 1 else ''}, "
                f"but {len(selected_ids)} were selected."
            )

        # --------------------------------------------------------------
        # No duplicate selection
        # --------------------------------------------------------------

        normalized_ids = [
            card_id.lower()
            for card_id in selected_ids
        ]

        if len(set(normalized_ids)) != len(
            normalized_ids
        ):
            raise ValueError(
                "The same Tarot card cannot be "
                "selected more than once."
            )

        # --------------------------------------------------------------
        # Resolve every selected card
        # --------------------------------------------------------------

        selected_cards: List[Dict[str, Any]] = []

        for card_id in selected_ids:

            card_data = self._find_card_by_id(
                card_id
            )

            if card_data is None:
                raise ValueError(
                    f"Selected Tarot card '{card_id}' "
                    f"was not found in the 78-card catalog."
                )

            selected_cards.append(
                card_data
            )

        # --------------------------------------------------------------
        # Build the revealed reading
        # --------------------------------------------------------------

        cards_drawn: List[Dict[str, Any]] = []

        for position, card_data in zip(
            positions,
            selected_cards,
        ):
            cards_drawn.append(
                self._build_card_result(
                    position=position,
                    card_data=card_data,
                    reversed_probability=reversed_probability,
                )
            )

        return {
            "spread_type": str(
                spread_type
            ).strip().lower(),
            "card_count": len(cards_drawn),
            "cards": cards_drawn,
            "selection_mode": "user_selected",
            "selected_card_ids": selected_ids,
        }


# ----------------------------------------------------------------------
# PATH RESOLUTION
# ----------------------------------------------------------------------

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

CATALOG_PATH = (
    BASE_DIR
    / "datasets"
    / "metadata"
    / "tarot_catalog.json"
)

# Fallback for execution from the backend root.
if not CATALOG_PATH.exists():
    CATALOG_PATH = (
        Path("datasets")
        / "metadata"
        / "tarot_catalog.json"
    )


# ----------------------------------------------------------------------
# ENGINE INSTANCE
# ----------------------------------------------------------------------

tarot_engine = TarotReadingEngine(
    str(CATALOG_PATH)
)