"""
Deleted case handling for FAERS.
Loads and purges retracted/deleted cases using AllDeletedCases.txt.
"""

import os
from typing import Set, Union, List
import glob


class DeletedCaseManager:
    """Manages the set of retracted or deleted FAERS case IDs."""

    def __init__(self, deleted_cases_path: Union[str, List[str], None] = None):
        self.deleted_cases: Set[str] = set()
        if deleted_cases_path:
            if isinstance(deleted_cases_path, (list, tuple, set)):
                for p in deleted_cases_path:
                    self.load_path(p)
            elif isinstance(deleted_cases_path, str):
                self.load_path(deleted_cases_path)

    def load_path(self, path: str) -> int:
        """Load deleted cases from a file path or scan a directory for deletion files."""
        if not os.path.exists(path):
            return 0
        if os.path.isdir(path):
            total_loaded = 0
            for root, _, files in os.walk(path):
                for f in files:
                    if "delete" in f.lower() and f.lower().endswith(".txt"):
                        total_loaded += self.load_deleted_cases(os.path.join(root, f))
            return total_loaded
        return self.load_deleted_cases(path)

    def load_deleted_cases(self, file_path: str) -> int:
        """Load deleted case IDs from an FDA deletion file (AllDeletedCases.txt or quarterly deletion text)."""
        if not os.path.exists(file_path):
            return 0
        initial_count = len(self.deleted_cases)
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                cid = line.strip()
                if cid:
                    self.deleted_cases.add(cid)
        new_loaded = len(self.deleted_cases) - initial_count
        return new_loaded

    def is_deleted(self, caseid: str) -> bool:
        """Check if a specific case ID is flagged as deleted."""
        return str(caseid).strip() in self.deleted_cases

    def __len__(self) -> int:
        return len(self.deleted_cases)
