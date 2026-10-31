"""
Multi-Tiered Evidence and Confidence Classification Engine.
Synthesizes observational FAERS signals, statistical baselines, and independent OMOP status.
ML signal evidence is strictly deactivated by default (use_ml_score=False)
until a validated model is trained and frozen.
"""

from typing import Optional


class EvidenceCategory:
    KNOWN_ESTABLISHED = "KNOWN / ESTABLISHED"
    SUPPORTED = "SUPPORTED"
    EMERGING = "EMERGING"
    NOVEL_POTENTIAL_SIGNAL = "NOVEL / POTENTIAL SIGNAL"
    UNKNOWN_INSUFFICIENT = "UNKNOWN / INSUFFICIENT EVIDENCE"


class EvidenceClassifier:
    """
    Classifies candidate drug-ADR pairs into multi-tiered clinical evidence categories.
    Operates safely in Phase 2 using only FAERS + PRR/ROR + OMOP reference evidence.
    """

    @staticmethod
    def classify_pair(
        omop_status: str,
        case_count_a: int,
        prr: Optional[float] = None,
        ror_lower_95: Optional[float] = None,
        ml_signal_score: Optional[float] = None,
        regulatory_warning: bool = False,
        use_ml_score: bool = False
    ) -> str:
        """
        Determine the standardized evidence category for a pair.

        Safety Invariants:
        1. When use_ml_score=False (Phase 2 default), ml_signal_score is completely ignored.
        2. Absence from OMOP is UNLISTED_UNKNOWN, never assumed negative.
        3. No default ML score can alter evidence tiers.
        """
        # Tier 1: KNOWN / ESTABLISHED
        # Established positive control in OMOP or explicit regulatory warning with solid report evidence
        if (omop_status == "POSITIVE_CONTROL" and case_count_a >= 3) or regulatory_warning:
            return EvidenceCategory.KNOWN_ESTABLISHED

        # Tier 2: SUPPORTED
        # Known in OMOP with minimal reports (< 3) OR elevated disproportionality with strong report volume
        if omop_status == "POSITIVE_CONTROL":
            return EvidenceCategory.SUPPORTED
        if (prr is not None and prr >= 2.0) and (ror_lower_95 is not None and ror_lower_95 > 1.0) and case_count_a >= 10:
            if not use_ml_score or (ml_signal_score is not None and ml_signal_score >= 0.65):
                return EvidenceCategory.SUPPORTED

        # Tier 3: EMERGING
        # Elevated disproportionality for an unlisted pair with sufficient volume
        if omop_status == "UNLISTED_UNKNOWN" and case_count_a >= 5:
            if (prr is not None and prr >= 2.0) or (ror_lower_95 is not None and ror_lower_95 > 1.0):
                if not use_ml_score or (ml_signal_score is not None and ml_signal_score >= 0.50):
                    return EvidenceCategory.EMERGING

        # Tier 4: NOVEL / POTENTIAL SIGNAL (Only active when ML model is enabled in future phases)
        if use_ml_score and ml_signal_score is not None:
            if omop_status == "UNLISTED_UNKNOWN" and case_count_a >= 3 and ml_signal_score >= 0.70:
                return EvidenceCategory.NOVEL_POTENTIAL_SIGNAL

        # Tier 5: UNKNOWN / INSUFFICIENT EVIDENCE
        # Default state for sparse reports, negative controls, or unconfirmed associations
        return EvidenceCategory.UNKNOWN_INSUFFICIENT
