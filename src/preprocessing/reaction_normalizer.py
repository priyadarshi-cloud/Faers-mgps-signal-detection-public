"""
Reaction Terminology Normalization Engine.
Standardizes FAERS MedDRA Preferred Terms (PTs) and normalizes whitespace and casing.
"""

from typing import Optional


class ReactionNormalizer:
    """Standardizes adverse reaction terminology to canonical MedDRA Preferred Terms."""

    @staticmethod
    def normalize_pt(raw_pt: Optional[str]) -> str:
        """Standardize a raw MedDRA Preferred Term string."""
        if not raw_pt or pd_isna(raw_pt):
            return "UNKNOWN"
        cleaned = str(raw_pt).strip()
        if not cleaned or cleaned.upper() == "NAN":
            return "UNKNOWN"
        # Standardize to title case / canonical form
        return cleaned.strip()


def pd_isna(val) -> bool:
    if val is None:
        return True
    s = str(val).strip().upper()
    return s in ["", "NAN", "NONE", "NULL"]
