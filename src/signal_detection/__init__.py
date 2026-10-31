"""
Signal Detection Module for FAERS AI Model.

Provides:
- DisproportionalityCalculator: Frequentist PRR and ROR with confidence intervals.
- EBGMEngine, MGPSHyperparameters, OptimizationResult: Empirical Bayes Geometric Mean
  and Multi-item Gamma Poisson Shrinker (MGPS) engine.
"""

from src.signal_detection.disproportionality import DisproportionalityCalculator
from src.signal_detection.ebgm_engine import (
    EBGMEngine,
    MGPSHyperparameters,
    OptimizationResult,
)

__all__ = [
    "DisproportionalityCalculator",
    "EBGMEngine",
    "MGPSHyperparameters",
    "OptimizationResult",
]
