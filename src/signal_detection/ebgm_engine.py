"""
Empirical Bayes Geometric Mean (EBGM) and Multi-item Gamma Poisson Shrinker (MGPS) Engine.

Mathematical Specification:
---------------------------
1. Contingency Matrix and Independence Null:
   For drug d and adverse event e:
   - a: co-occurrence count (observed N_ij)
   - b: drug total - a
   - c: event total - a
   - d: N_total - a - b - c
   - E_ij: expected co-occurrence count under independence:
     E_ij = ((a + b) * (a + c)) / N_total

2. Poisson Likelihood & Gamma Mixture Prior:
   - N_ij ~ Poisson(mu_ij), where mu_ij = lambda_ij * E_ij
   - lambda_ij is the true relative reporting ratio.
   - Prior distribution on lambda:
     pi(lambda | theta) = w * Gamma(alpha_1, beta_1) + (1 - w) * Gamma(alpha_2, beta_2)
     where theta = (alpha_1, beta_1, alpha_2, beta_2, w).

   PARAMETERIZATION CONVENTION:
   - Gamma distribution is strictly parameterized by SHAPE (alpha) and RATE (beta).
   - Probability density function:
     f(lambda; alpha, beta) = (beta^alpha / Gamma(alpha)) * lambda^(alpha - 1) * exp(-beta * lambda),  lambda > 0
   - Expected value: E[lambda] = alpha / beta
   - Variance: Var(lambda) = alpha / beta^2
   - In scipy.stats.gamma, shape is a = alpha and scale is scale = 1 / beta.
   - Mixture weight w in (0, 1) is the prior probability of Component 1.
   - Identifiability convention: alpha_1 / beta_1 <= alpha_2 / beta_2.

3. Marginal Negative Binomial Mixture Likelihood:
   Integrating out lambda_ij yields the marginal distribution of N_ij given E_ij:
   P(N_ij = n | E_ij, theta) = w * NB(n; alpha_1, beta_1 / (beta_1 + E_ij))
                             + (1 - w) * NB(n; alpha_2, beta_2 / (beta_2 + E_ij))
   where NB(n; alpha, p) = (Gamma(n + alpha) / (n! * Gamma(alpha))) * p^alpha * (1 - p)^n,
   with p = beta / (beta + E_ij).
   Evaluated in log-space using scipy.special.gammaln and scipy.special.logsumexp.

4. Posterior Distribution:
   lambda_ij | (N_ij = n, E_ij = E) ~ w* * Gamma(alpha_1 + n, beta_1 + E)
                                    + (1 - w*) * Gamma(alpha_2 + n, beta_2 + E)
   where posterior weight w* (or Q_n):
   w* = (w * NB(n; alpha_1, beta_1 / (beta_1 + E))) / P(n | E, theta)

5. Posterior Metrics:
   - EBGM (Empirical Bayes Geometric Mean):
     EBGM_ij = exp(E[ln lambda_ij | N_ij, E_ij])
     For a single Gamma(A, B) component, E[ln lambda] = psi(A) - ln(B), where psi is digamma.
     EBGM_ij = exp( w* * (psi(alpha_1 + n) - ln(beta_1 + E))
                  + (1 - w*) * (psi(alpha_2 + n) - ln(beta_2 + E)) )
   - EB05 (5th Percentile Lower Credibility Bound):
     Quantile q such that P(lambda_ij <= q | n, E) = 0.05.
     Solved via Brent root-finding (scipy.optimize.brentq) on the mixture CDF:
     F_post(q) = w* * F_Gamma(q; alpha_1 + n, beta_1 + E) + (1 - w*) * F_Gamma(q; alpha_2 + n, beta_2 + E) = 0.05.
   - EB95 (95th Percentile Upper Credibility Bound):
     Quantile q such that F_post(q) = 0.95.

Scientific Invariants:
----------------------
- EBGM/MGPS is strictly an unsupervised Bayesian signal prioritization metric.
- It does NOT establish pharmacological causality or clinical confirmation.
- OMOP and EU-ADR benchmarks are strictly quarantined for downstream evaluation and
  must NEVER be used to choose, fit, or calibrate EBGM hyperparameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import scipy.optimize as opt
import scipy.special as sp
import scipy.stats as st


@dataclass(frozen=True)
class MGPSHyperparameters:
    """
    Hyperparameters for the two-component Gamma mixture prior:
    pi(lambda) = w * Gamma(alpha_1, beta_1) + (1 - w) * Gamma(alpha_2, beta_2)

    PARAMETERIZATION: SHAPE-RATE convention.
    - alpha_1, alpha_2: shape parameters (alpha > 0)
    - beta_1, beta_2: rate parameters (beta > 0, scale = 1 / beta)
    - w: mixture weight for Component 1 (0 < w < 1)
    """
    alpha1: float
    beta1: float
    alpha2: float
    beta2: float
    w: float

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate hyperparameter domain boundaries."""
        if not (self.alpha1 > 0.0 and self.beta1 > 0.0):
            raise ValueError(f"Component 1 shape/rate must be strictly positive: alpha1={self.alpha1}, beta1={self.beta1}")
        if not (self.alpha2 > 0.0 and self.beta2 > 0.0):
            raise ValueError(f"Component 2 shape/rate must be strictly positive: alpha2={self.alpha2}, beta2={self.beta2}")
        if not (0.0 < self.w < 1.0):
            raise ValueError(f"Mixture weight w must be strictly in (0, 1), got {self.w}")

    def to_tuple(self) -> Tuple[float, float, float, float, float]:
        """Return parameters as (alpha1, beta1, alpha2, beta2, w)."""
        return (self.alpha1, self.beta1, self.alpha2, self.beta2, self.w)

    @classmethod
    def from_tuple(cls, params: Sequence[float]) -> MGPSHyperparameters:
        """Construct from (alpha1, beta1, alpha2, beta2, w)."""
        if len(params) != 5:
            raise ValueError(f"Expected 5 parameters, got {len(params)}")
        return cls(
            alpha1=float(params[0]),
            beta1=float(params[1]),
            alpha2=float(params[2]),
            beta2=float(params[3]),
            w=float(params[4]),
        )

    def mean_component1(self) -> float:
        """Prior mean for component 1: alpha1 / beta1."""
        return self.alpha1 / self.beta1

    def mean_component2(self) -> float:
        """Prior mean for component 2: alpha2 / beta2."""
        return self.alpha2 / self.beta2

    def canonicalize(self) -> MGPSHyperparameters:
        """
        Enforce identifiability convention: mean(Component 1) <= mean(Component 2).
        If mean(1) > mean(2), permute components: w -> 1 - w, and swap (alpha1, beta1) with (alpha2, beta2).
        """
        if self.mean_component1() > self.mean_component2():
            return MGPSHyperparameters(
                alpha1=self.alpha2,
                beta1=self.beta2,
                alpha2=self.alpha1,
                beta2=self.beta1,
                w=1.0 - self.w,
            )
        return self


@dataclass
class OptimizationResult:
    """Auditable diagnostics for hyperparameter optimization."""
    converged: bool
    hyperparameters: Optional[MGPSHyperparameters]
    log_likelihood: float
    iterations: int
    message: str
    starting_point: Tuple[float, float, float, float, float]
    standard_errors: Optional[Dict[str, float]] = None
    all_restarts: List[Dict[str, Any]] = field(default_factory=list)
    truncated_at: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize optimization result to audit dictionary."""
        return {
            "converged": bool(self.converged),
            "hyperparameters": self.hyperparameters.to_tuple() if self.hyperparameters else None,
            "hyperparameters_dict": {
                "alpha1": self.hyperparameters.alpha1 if self.hyperparameters else None,
                "beta1": self.hyperparameters.beta1 if self.hyperparameters else None,
                "alpha2": self.hyperparameters.alpha2 if self.hyperparameters else None,
                "beta2": self.hyperparameters.beta2 if self.hyperparameters else None,
                "w": self.hyperparameters.w if self.hyperparameters else None,
            } if self.hyperparameters else None,
            "log_likelihood": float(self.log_likelihood),
            "iterations": int(self.iterations),
            "message": str(self.message),
            "starting_point": list(self.starting_point),
            "standard_errors": self.standard_errors,
            "num_restarts_evaluated": len(self.all_restarts),
            "truncated_at": self.truncated_at,
        }


class EBGMEngine:
    """
    Robust, production-grade Empirical Bayes Geometric Mean (EBGM) and MGPS engine.
    Computes exact expected counts, marginal negative binomial mixture log-likelihood,
    multi-start L-BFGS-B optimization, closed-form posterior EBGM, and Brent-root quantiles.
    """

    # Parameter boundaries for optimization: alpha, beta in [1e-3, 100], w in [1e-4, 1 - 1e-4]
    PARAM_BOUNDS = [
        (1e-3, 100.0),  # alpha1
        (1e-3, 100.0),  # beta1
        (1e-3, 100.0),  # alpha2
        (1e-3, 100.0),  # beta2
        (1e-4, 1.0 - 1e-4),  # w
    ]

    # Standard diverse starting guesses spanning plausible prior regimes
    DEFAULT_INITIAL_GUESSES = [
        (0.2, 0.1, 2.0, 4.0, 0.3333),      # openEBGM default guess
        (1.0, 1.0, 2.0, 1.0, 0.20),        # moderate baseline
        (0.05, 0.5, 3.0, 1.0, 0.05),       # sparse baseline
        (0.5, 1.5, 1.5, 0.5, 0.50),        # balanced components
        (0.18, 0.53, 2.14, 0.57, 0.18),    # DuMouchel 1999 SRS reference regime
    ]

    def __init__(self, seed: int = 42) -> None:
        """
        Args:
            seed: Deterministic random seed for reproducibility.
        """
        self.seed = seed

    # -------------------------------------------------------------------------
    # 1. Expected Count Computation
    # -------------------------------------------------------------------------
    @staticmethod
    def calculate_expected_counts(
        a: Union[np.ndarray, pd.Series, Sequence[float]],
        b: Union[np.ndarray, pd.Series, Sequence[float]],
        c: Union[np.ndarray, pd.Series, Sequence[float]],
        total_n: int,
    ) -> np.ndarray:
        """
        Compute expected cell counts E under the null hypothesis of independence:
        E = ((a + b) * (a + c)) / total_n

        Args:
            a: Co-occurrence counts (drug d, event e).
            b: Drug total - a (drug d, other events).
            c: Event total - a (other drugs, event e).
            total_n: Total deduplicated case universe (N). Must be positive.

        Returns:
            np.ndarray of expected counts E. Non-negative, zero where marginals are zero.
        """
        if total_n <= 0:
            raise ValueError(f"Total case count total_n must be strictly positive, got {total_n}")

        a_arr = np.asarray(a, dtype=np.float64)
        b_arr = np.asarray(b, dtype=np.float64)
        c_arr = np.asarray(c, dtype=np.float64)

        if a_arr.shape != b_arr.shape or a_arr.shape != c_arr.shape:
            raise ValueError(f"Shape mismatch: a {a_arr.shape}, b {b_arr.shape}, c {c_arr.shape}")

        if np.any(a_arr < 0) or np.any(b_arr < 0) or np.any(c_arr < 0):
            raise ValueError("Cell counts a, b, c must be non-negative.")

        drug_total = a_arr + b_arr
        event_total = a_arr + c_arr

        expected = (drug_total * event_total) / float(total_n)
        return expected

    # -------------------------------------------------------------------------
    # 2. 2D Count Binning (Squashing for Scale)
    # -------------------------------------------------------------------------
    @staticmethod
    def squash_counts_2d(
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        decimals: int = 2,
        use_log: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Group pairs into 2D frequency bins to compress massive contingency tables
        for scalable negative binomial mixture likelihood optimization.

        BINNING CONVENTION:
        - When use_log=True (default, scientifically recommended):
          Bin Key = (n, round(log10(E), decimals))
          Preserves uniform relative precision (~2.3% per bin for decimals=2) across
          the entire dynamic range of E (from 1e-6 to 1e4), eliminating the massive
          distortion of linear rounding in sparse cells.
        - When use_log=False:
          Bin Key = (n, round(E, decimals)) [legacy linear binning].

        REPRESENTATIVE EXPECTED COUNTS:
        Within each bin, the representative expected count is the arithmetic mean
        of the raw expected counts (e_mean = mean(e_raw)), preserving sufficient statistics.

        INPUT VALIDATION:
        - All elements of E must be finite and strictly positive (E > 0).
          If any E <= 0 or non-finite, raises ValueError explicitly (no silent row loss).
        - Observed counts n must be non-negative integers.
        - Arrays n and e must have identical lengths.

        LIMITATIONS:
        - Approximation Error: Binning collapses distinct E values into a single representative
          arithmetic mean E_mean, introducing a slight approximation error relative to exact unbinned
          likelihood evaluation (~0.00013% relative likelihood error at decimals=2 on pilot data).
        - Positivity Requirement: Since log10 is undefined for non-positive numbers, all E must
          be strictly positive (E > 0). Zero marginals must be handled prior to binning.
        - Quantile Sensitivity: Likelihood optimization over binned data yields mixture parameters
          theta; posterior quantiles EB05/EB95 for individual pairs must still be evaluated using
          each pair's unbinned (n_i, E_i) to prevent quantile discretization artifacts.

        Args:
            n: Observed counts (must be finite non-negative integers).
            e: Expected counts (must be finite strictly positive floats).
            decimals: Precision for rounding log10(E) or E before grouping.
            use_log: If True, uses round(log10(E), decimals); if False, linear round(E, decimals).

        Returns:
            Tuple of (n_unique, e_mean, weights) as np.ndarrays.
        """
        n_float = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)

        if len(n_float) != len(e_arr):
            raise ValueError(f"Length mismatch: len(n)={len(n_float)}, len(e)={len(e_arr)}")

        if len(n_float) == 0:
            return (
                np.array([], dtype=np.int64),
                np.array([], dtype=np.float64),
                np.array([], dtype=np.float64),
            )

        if not np.all(np.isfinite(n_float)):
            raise ValueError("Observed counts n must be finite; NaN or Inf encountered.")

        if np.any(n_float < 0):
            raise ValueError("Observed counts n must be non-negative.")

        if not np.all(np.equal(np.mod(n_float, 1.0), 0.0)):
            raise ValueError("Observed counts n must be integers.")

        n_arr = n_float.astype(np.int64)

        if not np.all(np.isfinite(e_arr)):
            raise ValueError("Expected counts E must be finite; NaN or Inf encountered.")

        if np.any(e_arr <= 0.0):
            raise ValueError("Expected counts E must be strictly positive (E > 0) for logarithmic binning.")

        if use_log:
            e_bin_key = np.round(np.log10(e_arr), decimals=decimals)
        else:
            e_bin_key = np.round(e_arr, decimals=decimals)

        df = pd.DataFrame({
            "n": n_arr,
            "bin_key": e_bin_key,
            "e_raw": e_arr,
        })
        grouped = df.groupby(["n", "bin_key"]).agg(
            e_mean=("e_raw", "mean"),
            weight=("e_raw", "count"),
        ).reset_index()

        return (
            grouped["n"].to_numpy(dtype=np.int64),
            grouped["e_mean"].to_numpy(dtype=np.float64),
            grouped["weight"].to_numpy(dtype=np.float64),
        )

    # -------------------------------------------------------------------------
    # 3. Marginal Likelihood Evaluation
    # -------------------------------------------------------------------------
    @staticmethod
    def _log_nb_pmf(
        n: np.ndarray,
        e: np.ndarray,
        alpha: float,
        beta: float,
    ) -> np.ndarray:
        """
        Numerically stable log probability mass function of Negative Binomial:
        log NB(n; alpha, p=beta/(beta+E))
        = gammaln(n + alpha) - gammaln(alpha) - gammaln(n + 1)
          + alpha * ln(beta / (beta + E)) + n * ln(E / (beta + E))
        """
        # When n == 0, n * ln(E / (beta + E)) is analytically 0, even if E is tiny.
        p = beta / (beta + e)
        q = e / (beta + e)

        log_comb = sp.gammaln(n + alpha) - sp.gammaln(alpha) - sp.gammaln(n + 1.0)
        log_prob = log_comb + alpha * np.log(p)

        nonzero_mask = n > 0
        if np.any(nonzero_mask):
            # When E == 0 and n > 0, probability is 0 (log PMF = -inf). Avoid log(0) runtime warning:
            safe_q = np.where(nonzero_mask & (q > 0.0), q, 1.0)
            log_q = np.where(q > 0.0, np.log(safe_q), -1e12)
            log_prob = log_prob + np.where(nonzero_mask, n * log_q, 0.0)

        return log_prob

    @classmethod
    def calculate_mixture_probabilities(
        cls,
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        theta: MGPSHyperparameters,
    ) -> np.ndarray:
        """
        Calculate unconditional mixture PMF P(N = n | E, theta) for arbitrary non-negative counts n:
        P(N = n | E, theta) = w * NB(n; alpha_1, p_1) + (1 - w) * NB(n; alpha_2, p_2)
        where p_k = beta_k / (beta_k + E).
        """
        n_arr = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)
        alpha1, beta1, alpha2, beta2, w = theta.to_tuple()
        log_f1 = cls._log_nb_pmf(n_arr, e_arr, alpha1, beta1)
        log_f2 = cls._log_nb_pmf(n_arr, e_arr, alpha2, beta2)
        stack = np.column_stack([
            math.log(w) + log_f1,
            math.log(1.0 - w) + log_f2,
        ])
        log_marg = sp.logsumexp(stack, axis=1)
        return np.exp(log_marg)

    @classmethod
    def calculate_truncation_probabilities(
        cls,
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        theta: MGPSHyperparameters,
        truncated_at: int = 2,
    ) -> np.ndarray:
        """
        Calculate observation selection / survival probability P(N >= truncated_at | E, theta) across E.

        MATHEMATICAL DERIVATION:
        Under the Negative Binomial mixture, for each component k in {1, 2}:
        P(N >= k_thresh | E, alpha_k, beta_k) = 1 - sum_{m=0}^{k_thresh-1} NB(m; alpha_k, p_k)
        By the exact Negative Binomial CDF identity with the Regularized Incomplete Beta function:
        P(N >= k_thresh) = I_{q_k}(k_thresh, alpha_k) = scipy.special.betainc(k_thresh, alpha_k, q_k)
        where q_k = E / (beta_k + E).

        Full mixture selection probability:
        P(N >= k_thresh | E, theta) = w * betainc(k_thresh, alpha_1, q_1) + (1 - w) * betainc(k_thresh, alpha_2, q_2).

        This representation avoids catastrophic floating-point cancellation 1 - (P(0) + P(1)) when E is small.
        """
        e_arr = np.asarray(e, dtype=np.float64)
        if truncated_at not in (1, 2):
            raise ValueError(f"Unsupported truncation threshold: {truncated_at}. Supported: 1 or 2.")
        if np.any(e_arr <= 0.0) or not np.all(np.isfinite(e_arr)):
            raise ValueError("Expected counts E must be strictly positive and finite.")
        alpha1, beta1, alpha2, beta2, w = theta.to_tuple()
        q1 = e_arr / (beta1 + e_arr)
        q2 = e_arr / (beta2 + e_arr)
        k_val = float(truncated_at)
        p_comp1 = sp.betainc(k_val, alpha1, q1)
        p_comp2 = sp.betainc(k_val, alpha2, q2)
        p_mix = w * p_comp1 + (1.0 - w) * p_comp2
        return np.clip(p_mix, 0.0, 1.0)

    @classmethod
    def negative_log_likelihood(
        cls,
        theta_tuple: Sequence[float],
        n: np.ndarray,
        e: np.ndarray,
        weights: Optional[np.ndarray] = None,
        truncated_at: Optional[int] = None,
    ) -> float:
        """
        Calculate total negative log-likelihood across counts n, e with optional weights:
        - When truncated_at is None (default):
          Ordinary un-truncated negative log-likelihood:
          -ln L(theta) = - sum_k [ W_k * ln ( w * P(n_k | E_k, a1, b1) + (1 - w) * P(n_k | E_k, a2, b2) ) ]
        - When truncated_at is not None (e.g. truncated_at = 2):
          Conditional truncated negative log-likelihood:
          -ln L_trunc(theta) = - sum_k [ W_k * ( ln P(n_k | E_k, theta) - ln P(N >= truncated_at | E_k, theta) ) ]
        """
        alpha1, beta1, alpha2, beta2, w = theta_tuple

        # Strict boundary protection
        if alpha1 <= 0.0 or beta1 <= 0.0 or alpha2 <= 0.0 or beta2 <= 0.0 or not (0.0 < w < 1.0):
            return 1e12

        # Log PMFs for both components
        log_f1 = cls._log_nb_pmf(n, e, alpha1, beta1)
        log_f2 = cls._log_nb_pmf(n, e, alpha2, beta2)

        # Log marginal mixture using logsumexp for numerical stability:
        stack = np.column_stack([
            math.log(w) + log_f1,
            math.log(1.0 - w) + log_f2,
        ])
        log_marginal = sp.logsumexp(stack, axis=1)

        # Conditional likelihood normalization if truncated
        if truncated_at is not None:
            if truncated_at not in (1, 2):
                raise ValueError(f"Unsupported truncation threshold: {truncated_at}. Supported: 1 or 2.")
            k_val = float(truncated_at)
            q1 = e / (beta1 + e)
            q2 = e / (beta2 + e)
            p_comp1 = np.maximum(sp.betainc(k_val, alpha1, q1), 1e-300)
            p_comp2 = np.maximum(sp.betainc(k_val, alpha2, q2), 1e-300)
            stack_trunc = np.column_stack([
                math.log(w) + np.log(p_comp1),
                math.log(1.0 - w) + np.log(p_comp2),
            ])
            log_p_trunc = sp.logsumexp(stack_trunc, axis=1)
            log_marginal = log_marginal - log_p_trunc

        if weights is not None:
            neg_ll = -np.sum(weights * log_marginal)
        else:
            neg_ll = -np.sum(log_marginal)

        if not np.isfinite(neg_ll):
            return 1e12

        return float(neg_ll)

    # -------------------------------------------------------------------------
    # 4. Hyperparameter Fitting (Multi-Start L-BFGS-B)
    # -------------------------------------------------------------------------
    def fit(
        self,
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        weights: Optional[Union[np.ndarray, pd.Series, Sequence[float]]] = None,
        initial_guesses: Optional[List[Tuple[float, float, float, float, float]]] = None,
        compute_se: bool = True,
        truncated_at: Optional[int] = None,
    ) -> OptimizationResult:
        """
        Estimate mixture hyperparameters theta = (alpha1, beta1, alpha2, beta2, w)
        using multi-start L-BFGS-B optimization on the marginal negative binomial mixture.

        Args:
            n: Observed counts (must be non-negative integers; if truncated_at is set, n >= truncated_at).
            e: Expected counts (must be strictly positive for likelihood estimation).
            weights: Optional frequency weights (for 2D squashed/binned tables).
            initial_guesses: Optional list of 5-tuples for starting points.
            compute_se: Whether to estimate asymptotic standard errors via numerical Hessian.
            truncated_at: Optional minimum count threshold (e.g. 2 for n >= 2 selected candidate pairs).
                          If None (default), fits standard un-truncated Negative Binomial mixture.
                          If 1 or 2, conditions likelihood on P(N >= truncated_at | E, theta).

        Returns:
            OptimizationResult containing best estimates, convergence flag, and diagnostics.
        """
        n_arr = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)
        w_arr = np.asarray(weights, dtype=np.float64) if weights is not None else None

        if len(n_arr) != len(e_arr):
            raise ValueError(f"Length mismatch: len(n)={len(n_arr)}, len(e)={len(e_arr)}")

        if len(n_arr) == 0:
            return OptimizationResult(
                converged=False,
                hyperparameters=None,
                log_likelihood=float("-inf"),
                iterations=0,
                message="Cannot fit model: input dataset is empty.",
                starting_point=(0.0, 0.0, 0.0, 0.0, 0.0),
                truncated_at=truncated_at,
            )

        if truncated_at is not None:
            if truncated_at not in (1, 2):
                raise ValueError(f"Unsupported truncation threshold: {truncated_at}. Supported: 1 or 2.")
            if np.any(n_arr < truncated_at):
                raise ValueError(
                    f"Observed counts n contain values below truncation threshold {truncated_at} "
                    f"(min n = {np.min(n_arr)}). Dataset must satisfy n >= {truncated_at}."
                )

        # Filter out invalid cells for likelihood estimation (e must be > 0)
        valid_mask = (e_arr > 0.0) & (n_arr >= 0.0)
        if not np.all(valid_mask):
            n_arr = n_arr[valid_mask]
            e_arr = e_arr[valid_mask]
            if w_arr is not None:
                w_arr = w_arr[valid_mask]

        if len(n_arr) == 0:
            return OptimizationResult(
                converged=False,
                hyperparameters=None,
                log_likelihood=float("-inf"),
                iterations=0,
                message="Cannot fit model: zero valid rows with E > 0.",
                starting_point=(0.0, 0.0, 0.0, 0.0, 0.0),
                truncated_at=truncated_at,
            )

        guesses = initial_guesses if initial_guesses is not None else self.DEFAULT_INITIAL_GUESSES

        best_res: Optional[opt.OptimizeResult] = None
        best_loss = float("inf")
        best_guess = guesses[0]
        restarts_log = []

        for guess in guesses:
            try:
                res = opt.minimize(
                    fun=self.negative_log_likelihood,
                    x0=guess,
                    args=(n_arr, e_arr, w_arr, truncated_at),
                    method="L-BFGS-B",
                    bounds=self.PARAM_BOUNDS,
                    options={"maxiter": 500, "ftol": 1e-9, "gtol": 1e-6},
                )
                restarts_log.append({
                    "start": list(guess),
                    "success": bool(res.success),
                    "fun": float(res.fun),
                    "nit": int(res.nit),
                    "message": str(res.message),
                    "params": list(res.x) if res.x is not None else None,
                })

                if res.success and res.fun < best_loss:
                    best_loss = res.fun
                    best_res = res
                    best_guess = guess
            except Exception as exc:
                restarts_log.append({
                    "start": list(guess),
                    "success": False,
                    "error": str(exc),
                })

        if best_res is None or not best_res.success:
            return OptimizationResult(
                converged=False,
                hyperparameters=None,
                log_likelihood=-best_loss if best_loss < float("inf") else float("-inf"),
                iterations=0 if best_res is None else best_res.nit,
                message="Optimizer failed to converge across all starting points." if best_res is None else best_res.message,
                starting_point=best_guess,
                all_restarts=restarts_log,
                truncated_at=truncated_at,
            )

        # Build hyperparameters and enforce canonical identifiability
        raw_hypers = MGPSHyperparameters.from_tuple(best_res.x)
        canonical_hypers = raw_hypers.canonicalize()

        # Compute standard errors if requested
        se_dict: Optional[Dict[str, float]] = None
        if compute_se:
            se_dict = self._compute_standard_errors(canonical_hypers, n_arr, e_arr, w_arr, truncated_at=truncated_at)

        return OptimizationResult(
            converged=True,
            hyperparameters=canonical_hypers,
            log_likelihood=-best_res.fun,
            iterations=best_res.nit,
            message=best_res.message,
            starting_point=best_guess,
            standard_errors=se_dict,
            all_restarts=restarts_log,
            truncated_at=truncated_at,
        )

    def _compute_standard_errors(
        self,
        hypers: MGPSHyperparameters,
        n: np.ndarray,
        e: np.ndarray,
        weights: Optional[np.ndarray],
        truncated_at: Optional[int] = None,
    ) -> Optional[Dict[str, float]]:
        """Compute asymptotic standard errors via numerical Hessian inversion (observed Fisher info)."""
        try:
            x0 = np.array(hypers.to_tuple(), dtype=np.float64)
            eps = 1e-4

            def loss_fn(p):
                return self.negative_log_likelihood(p, n, e, weights, truncated_at=truncated_at)

            # Central difference Hessian
            dim = len(x0)
            hess = np.zeros((dim, dim))
            for i in range(dim):
                for j in range(i, dim):
                    if i == j:
                        dx = np.zeros(dim)
                        dx[i] = eps
                        f_plus = loss_fn(x0 + dx)
                        f_minus = loss_fn(x0 - dx)
                        f_0 = loss_fn(x0)
                        hess[i, i] = (f_plus - 2.0 * f_0 + f_minus) / (eps ** 2)
                    else:
                        dxi = np.zeros(dim)
                        dxi[i] = eps
                        dxj = np.zeros(dim)
                        dxj[j] = eps
                        f_pp = loss_fn(x0 + dxi + dxj)
                        f_pm = loss_fn(x0 + dxi - dxj)
                        f_mp = loss_fn(x0 - dxi + dxj)
                        f_mm = loss_fn(x0 - dxi - dxj)
                        hess[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4.0 * eps ** 2)
                        hess[j, i] = hess[i, j]

            # Invert Hessian: Cov = H^-1
            cov = np.linalg.pinv(hess)
            variances = np.diag(cov)
            se_vals = [math.sqrt(max(0.0, v)) for v in variances]
            param_names = ["alpha1_se", "beta1_se", "alpha2_se", "beta2_se", "w_se"]
            return dict(zip(param_names, se_vals))
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # 5. Posterior Weight (Q_n) Computation
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_posterior_weights(
        cls,
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        theta: MGPSHyperparameters,
    ) -> np.ndarray:
        """
        Calculate posterior probability Q_n (w*) that lambda belongs to Component 1:
        w* = w * P(n | E, a1, b1) / [ w * P(n | E, a1, b1) + (1 - w) * P(n | E, a2, b2) ]

        Evaluated in log space to guarantee numerical stability.
        Returns np.ndarray of probabilities in [0.0, 1.0].
        """
        n_arr = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)

        alpha1, beta1, alpha2, beta2, w = theta.to_tuple()

        log_f1 = cls._log_nb_pmf(n_arr, e_arr, alpha1, beta1)
        log_f2 = cls._log_nb_pmf(n_arr, e_arr, alpha2, beta2)

        stack = np.column_stack([
            math.log(w) + log_f1,
            math.log(1.0 - w) + log_f2,
        ])
        log_marginal = sp.logsumexp(stack, axis=1)
        log_num = math.log(w) + log_f1
        valid_marginal = np.isfinite(log_marginal) & (log_marginal > -1e10)
        safe_diff = np.where(valid_marginal, log_num - log_marginal, math.log(w))
        qn = np.clip(np.exp(safe_diff), 0.0, 1.0)
        return qn

    # -------------------------------------------------------------------------
    # 6. Posterior EBGM Computation
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_ebgm(
        cls,
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        theta: MGPSHyperparameters,
        q_n: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Compute Empirical Bayes Geometric Mean (EBGM) in closed form:
        EBGM = exp( E[ln lambda | n, E] )
             = exp( w* * [psi(alpha_1 + n) - ln(beta_1 + E)]
                  + (1 - w*) * [psi(alpha_2 + n) - ln(beta_2 + E)] )

        Args:
            n: Observed counts.
            e: Expected counts.
            theta: Fitted hyperparameters.
            q_n: Optional precomputed posterior weights.

        Returns:
            np.ndarray of EBGM values. NaN for cells where E <= 0.
        """
        n_arr = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)

        if q_n is None:
            qn_arr = cls.calculate_posterior_weights(n_arr, e_arr, theta)
        else:
            qn_arr = np.asarray(q_n, dtype=np.float64)

        alpha1, beta1, alpha2, beta2, _ = theta.to_tuple()

        # Closed-form expected log lambda for Component 1 and 2
        e_log_lam1 = sp.digamma(alpha1 + n_arr) - np.log(beta1 + e_arr)
        e_log_lam2 = sp.digamma(alpha2 + n_arr) - np.log(beta2 + e_arr)

        expected_log_lambda = qn_arr * e_log_lam1 + (1.0 - qn_arr) * e_log_lam2
        ebgm = np.exp(expected_log_lambda)

        # Invalid expected counts (E <= 0) produce NaN
        invalid_mask = e_arr <= 0.0
        if np.any(invalid_mask):
            ebgm = np.where(invalid_mask, np.nan, ebgm)

        return ebgm

    # -------------------------------------------------------------------------
    # 7. Posterior Quantiles (EB05, EB95) via Brent Root-Finding
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_posterior_quantiles(
        cls,
        n: Union[np.ndarray, pd.Series, Sequence[float]],
        e: Union[np.ndarray, pd.Series, Sequence[float]],
        theta: MGPSHyperparameters,
        quantiles: Sequence[float] = (0.05, 0.95),
        q_n: Optional[np.ndarray] = None,
    ) -> Dict[float, np.ndarray]:
        """
        Calculate posterior quantiles q_p solving F_post(q_p | n, E) = p
        via Brent's root-finding method on the mixture Gamma CDF:
        F_post(q) = w* * F_Gamma(q; alpha_1 + n, beta_1 + E)
                  + (1 - w*) * F_Gamma(q; alpha_2 + n, beta_2 + E) = p

        TIGHT BOUNDING CONVENTION:
        For probability p, the mixture quantile q_p is guaranteed to lie within:
        [ min(q_p1, q_p2), max(q_p1, q_p2) ]
        where q_pk is the exact quantile of Component k (scipy.stats.gamma.ppf).

        Args:
            n: Observed counts.
            e: Expected counts.
            theta: Fitted hyperparameters.
            quantiles: Tuple of target probabilities (e.g. 0.05 for EB05, 0.95 for EB95).
            q_n: Optional precomputed posterior weights.

        Returns:
            Dict mapping quantile probability p to np.ndarray of values.
        """
        n_arr = np.asarray(n, dtype=np.float64)
        e_arr = np.asarray(e, dtype=np.float64)

        for p in quantiles:
            if not (0.0 < p < 1.0):
                raise ValueError(f"Quantile probability must be in (0, 1), got {p}")

        if q_n is None:
            qn_arr = cls.calculate_posterior_weights(n_arr, e_arr, theta)
        else:
            qn_arr = np.asarray(q_n, dtype=np.float64)

        alpha1, beta1, alpha2, beta2, _ = theta.to_tuple()
        results: Dict[float, np.ndarray] = {p: np.full(len(n_arr), np.nan) for p in quantiles}

        for i in range(len(n_arr)):
            ni = n_arr[i]
            ei = e_arr[i]
            wi = qn_arr[i]

            if ei <= 0.0 or not np.isfinite(ei) or not np.isfinite(ni) or ni < 0.0:
                continue

            shape1, scale1 = alpha1 + ni, 1.0 / (beta1 + ei)
            shape2, scale2 = alpha2 + ni, 1.0 / (beta2 + ei)

            for p in quantiles:
                # Component exact quantiles
                q1 = st.gamma.ppf(p, a=shape1, scale=scale1)
                q2 = st.gamma.ppf(p, a=shape2, scale=scale2)

                if abs(q1 - q2) < 1e-12:
                    results[p][i] = q1
                    continue

                low_b = max(1e-12, min(q1, q2) * 0.999)
                high_b = max(q1, q2) * 1.001

                def cdf_diff(q_val: float) -> float:
                    c1 = st.gamma.cdf(q_val, a=shape1, scale=scale1)
                    c2 = st.gamma.cdf(q_val, a=shape2, scale=scale2)
                    return float(wi * c1 + (1.0 - wi) * c2 - p)

                try:
                    q_root = opt.brentq(cdf_diff, low_b, high_b, xtol=1e-8, maxiter=100)
                    results[p][i] = q_root
                except Exception:
                    # Fallback wider bracket if extreme numerical roundoff
                    try:
                        q_root = opt.brentq(cdf_diff, 1e-12, high_b * 10.0, xtol=1e-8, maxiter=100)
                        results[p][i] = q_root
                    except Exception:
                        results[p][i] = np.nan

        return results

    # -------------------------------------------------------------------------
    # 8. Full Disproportionality Scoring Pipeline
    # -------------------------------------------------------------------------
    def score_candidate_pairs(
        self,
        df: pd.DataFrame,
        theta: MGPSHyperparameters,
        n_col: str = "a",
        e_col: str = "e_expected",
    ) -> pd.DataFrame:
        """
        Enrich candidate pairs DataFrame with posterior EBGM, EB05, EB95, and signal flags.

        Outputs added:
        - ebgm: Empirical Bayes Geometric Mean
        - eb05: 5th percentile lower credibility bound
        - eb95: 95th percentile upper credibility bound
        - ebgm_qn: Posterior weight for component 1
        - signal_eb05_conservative: Flag where EB05 >= 2.0 (FDA standard high-priority)
        - signal_eb05_permissive: Flag where EB05 >= 1.0 (reporting exceeds background)

        Returns:
            Enriched DataFrame copy.
        """
        out = df.copy()
        n_vals = out[n_col].to_numpy(dtype=np.float64)
        e_vals = out[e_col].to_numpy(dtype=np.float64)

        qn = self.calculate_posterior_weights(n_vals, e_vals, theta)
        ebgm = self.calculate_ebgm(n_vals, e_vals, theta, q_n=qn)
        quantiles = self.calculate_posterior_quantiles(
            n_vals, e_vals, theta, quantiles=(0.05, 0.95), q_n=qn
        )

        out["ebgm_qn"] = qn
        out["ebgm"] = ebgm
        out["eb05"] = quantiles[0.05]
        out["eb95"] = quantiles[0.95]

        out["signal_eb05_conservative"] = out["eb05"] >= 2.0
        out["signal_eb05_permissive"] = out["eb05"] >= 1.0

        return out
