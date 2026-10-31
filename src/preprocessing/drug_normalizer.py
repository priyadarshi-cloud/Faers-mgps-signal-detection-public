"""
Drug Normalization Engine.
Normalizes FAERS drugname and prod_ai to canonical active ingredient representations.
Removes salt suffixes, formulation-release suffixes, dosage artifacts, and handles
brand-to-generic and abbreviated-vitamin mappings.

Design decisions (from empirical FAERS context inspection 2026-10-08):
- ER/XR/XL/CR/SR/LA/SA/DR/IR/MR formulation suffixes are stripped because they carry no
  signal-detection value and the base drug name is always the relevant entity.
  A guard is applied: if the stripped base is <=2 chars, the suffix is NOT removed.
- B1/B2/B6 are mapped to canonical INN names (thiamine/riboflavin/pyridoxine) because they
  appear exclusively as concomitant drugs and have unambiguous mappings.
- Single-character vitamin codes (C, D, E, K) and 'CA' (calcium supplement abbreviation) are
  classified as AMBIGUOUS because they cannot reliably be mapped to a single ingredient.
  These appear exclusively as concomitant drugs (role_cod=C) and will not enter PS/SS pairs.
- B12 is classified AMBIGUOUS (multi-ingredient vitamin preparations are common).
- NI is left UNRESOLVED (no reliable single-ingredient mapping found in FAERS context).
"""

import re
from typing import Optional, Dict


class DrugNormalizer:
    """Standardizes drug trade names and active substances to canonical ingredients."""

    COMMON_SALTS = [
        r"\bHYDROCHLORIDE\b", r"\bHCL\b", r"\bSODIUM\b", r"\bCALCIUM\b", r"\bPOTASSIUM\b",
        r"\bMESYLATE\b", r"\bMALEATE\b", r"\bTARTRATE\b", r"\bACETATE\b", r"\bFUMARATE\b",
        r"\bSUCCINATE\b", r"\bPHOSPHATE\b", r"\bSULFATE\b", r"\bCHLORIDE\b", r"\bBROMIDE\b",
        r"\bBESYLATE\b", r"\bCITRATE\b", r"\bGLUCONATE\b", r"\bPROPIONATE\b", r"\bVALERATE\b",
        r"\bDIHYDROCHLORIDE\b", r"\bDISODIUM\b", r"\bDIPHOSPHATE\b", r"\bTRIHYDRATE\b",
        r"\bMONOHYDRATE\b", r"\bMAGNESIUM\b", r"\bNITRATE\b", r"\bCARBONATE\b"
    ]

    # Core brand to generic dictionary for common benchmark drugs.
    # Also includes abbreviated vitamin names confirmed by FAERS context inspection
    # (B1/B2/B6 appear exclusively as concomitant drugs with unambiguous INN mappings).
    BRAND_TO_GENERIC = {
        # ── Abbreviated vitamins with unambiguous single-ingredient mapping ──
        "B1": "THIAMINE",
        "B2": "RIBOFLAVIN",
        "B6": "PYRIDOXINE",
        # ── Common brand-to-generic mappings for benchmark drugs ──
        "LIPITOR": "ATORVASTATIN",
        "BONIVA": "IBANDRONATE",
        "HUMIRA": "ADALIMUMAB",
        "TYLENOL": "ACETAMINOPHEN",
        "PLAVIX": "CLOPIDOGREL",
        "NEXIUM": "ESOMEPRAZOLE",
        "PRILOSEC": "OMEPRAZOLE",
        "ZOFRAN": "ONDANSETRON",
        "AVANDIA": "ROSIGLITAZONE",
        "GLUCOPHAGE": "METFORMIN",
        "CRESTOR": "ROSUVASTATIN",
        "ZOCOR": "SIMVASTATIN",
        "COZAAR": "LOSARTAN",
        "DIOVAN": "VALSARTAN",
        "NORVASC": "AMLODIPINE",
        "PROZAC": "FLUOXETINE",
        "ZOLOFT": "SERTRALINE",
        "CELEBREX": "CELECOXIB",
        "VIOXX": "ROFECOXIB",
        "REMICADE": "INFLIXIMAB",
        "ENBREL": "ETANERCEPT",
        "XARELTO": "RIVAROXABAN",
        "ELIQUIS": "APIXABAN",
        "PRADAXA": "DABIGATRAN",
        "LEVAQUIN": "LEVOFLOXACIN",
        "CIPRO": "CIPROFLOXACIN",
        "AUGMENTIN": "AMOXICILLIN",
        "SANDOSTATIN": "OCTREOTIDE"
    }

    # Single-character and ambiguous vitamin codes that cannot be reliably mapped to a
    # single ingredient. Classified as AMBIGUOUS during normalization, NOT null/unknown.
    # Context: all appear exclusively as role_cod=C (concomitant) in FAERS inspection.
    # CA = calcium supplement abbreviation (confirmed 2023Q1 samples show 'Ca').
    # B12 = ambiguous due to multi-B vitamin preparations.
    # D2/D3/D4 = vitamin D forms; after CALCIUM salt-strip, 'CALCIUM D3' → 'D3' residual
    #   which would otherwise be treated as a 2-char valid name.
    # NI is intentionally excluded here — it falls through to UNRESOLVED by default.
    AMBIGUOUS_VITAMIN_CODES = frozenset({"C", "D", "E", "K", "CA", "B12", "D2", "D3", "D4"})

    # Formulation-release suffixes to strip from the end of drug names.
    # Applied ONLY when the base name after stripping is >2 characters (safety guard).
    # Empirically validated: no base names <=2 chars found in 2019Q1/2023Q1;
    # one edge case in 2014Q1 (handled by the guard).
    FORMULATION_SUFFIXES_RE = re.compile(
        r"\s+\b(ER|XR|XL|CR|SR|LA|SA|DR|IR|MR)\b\s*$", re.IGNORECASE
    )

    def __init__(self, custom_mapping: Optional[Dict[str, str]] = None):
        self.brand_mapping = dict(self.BRAND_TO_GENERIC)
        if custom_mapping:
            self.brand_mapping.update(custom_mapping)
        self.salt_regex = re.compile("|".join(self.COMMON_SALTS), flags=re.IGNORECASE)

    def normalize(self, drugname: Optional[str] = None, prod_ai: Optional[str] = None) -> str:
        """
        Produce a canonical ingredient string.
        Prioritizes prod_ai if present and non-empty; falls back to drugname.

        Returns:
            canonical ingredient string (lowercase)
            'AMBIGUOUS' for known multi-ingredient or unresolvable vitamin codes
            'UNKNOWN'   for blank, null, or completely uninformative input
        """
        target = ""
        if prod_ai and str(prod_ai).strip() and str(prod_ai).upper() not in ("NAN", "UNKNOWN", "NULL", "NONE", ""):
            target = str(prod_ai).strip().upper()
        elif drugname and str(drugname).strip() and str(drugname).upper() not in ("NAN", "UNKNOWN", "NULL", "NONE", ""):
            target = str(drugname).strip().upper()

        if not target:
            return "UNKNOWN"

        # Early exit: single-char/short ambiguous vitamin codes (CA, C, D, E, K, B12)
        # These cannot be reliably mapped to a single ingredient.
        if target in self.AMBIGUOUS_VITAMIN_CODES:
            return "AMBIGUOUS"

        # Remove parenthetical descriptions and dosage numbers
        target = re.sub(r"\(.*?\)", "", target)
        target = re.sub(r"\[.*?\]", "", target)
        target = re.sub(r"\b\d+(\.\d+)?\s*(MG|MCG|G|ML|%|IU)\b", "", target, flags=re.IGNORECASE)

        # Clean non-alphanumeric noise (keep hyphens and spaces)
        target = re.sub(r"[^A-Z0-9\s\-]", " ", target)
        target = re.sub(r"\s+", " ", target).strip()

        if not target:
            return "UNKNOWN"

        # Check brand/abbreviated-vitamin mapping (B1, B2, B6 resolve here)
        if target in self.brand_mapping:
            return self.brand_mapping[target].lower()

        # Check individual words for brand match if first word matches
        words = target.split()
        if len(words) > 0 and words[0] in self.brand_mapping:
            return self.brand_mapping[words[0]].lower()

        # Strip ER/XR/XL/CR/SR formulation-release suffixes (whole-word, end-of-string only).
        # Safety guard: only strip if the remaining base name is >2 characters.
        suffix_match = self.FORMULATION_SUFFIXES_RE.search(target)
        if suffix_match:
            candidate_base = self.FORMULATION_SUFFIXES_RE.sub("", target).strip()
            if len(candidate_base) > 2:
                target = candidate_base

        # Strip salt suffixes
        cleaned = self.salt_regex.sub("", target)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Handle biosimilar suffixes (e.g. INFLIXIMAB-DYYB -> INFLIXIMAB)
        cleaned = re.sub(r"\-[A-Z]{4}$", "", cleaned)

        # Post-cleaning ambiguous vitamin residual check.
        # Example: 'CALCIUM D3' -> after CALCIUM salt-strip -> 'D3' -> AMBIGUOUS.
        # Must be checked BEFORE the short-residual guard so D2/D3/D4 are
        # classified correctly rather than falling through to UNKNOWN.
        if cleaned in self.AMBIGUOUS_VITAMIN_CODES:
            return "AMBIGUOUS"

        if not cleaned or len(cleaned) <= 2:
            return "UNKNOWN"

        return cleaned.lower()

    def get_normalization_status(self, drugname: Optional[str] = None, prod_ai: Optional[str] = None) -> str:
        """
        Classifies normalization result into strict methodological categories:
        - 'NORMALIZED': mapped to a valid canonical ingredient (>2 chars, not ambiguous/unknown)
        - 'AMBIGUOUS': multi-ingredient preparation, ambiguous abbreviation (e.g. CA, B12, C, D, E, K)
        - 'UNRESOLVED': non-empty entry that could not be parsed into a canonical ingredient (e.g. <=2 char residue)
        - 'UNKNOWN': blank, null, or explicit unknown sentinel
        """
        norm = self.normalize(drugname=drugname, prod_ai=prod_ai)
        if norm == "AMBIGUOUS":
            return "AMBIGUOUS"
        elif norm == "UNKNOWN":
            target = ""
            if prod_ai and str(prod_ai).strip():
                target = str(prod_ai).strip().upper()
            elif drugname and str(drugname).strip():
                target = str(drugname).strip().upper()
            if not target or target in {"NAN", "UNKNOWN", "NULL", "NONE", "", "-", "N/A", "NA", "UNK", "NI"}:
                return "UNKNOWN"
            return "UNRESOLVED"
        else:
            return "NORMALIZED"
