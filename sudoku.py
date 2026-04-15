"""
sudoku.py
=============
CSP-based Sudoku Solver using:
  - AC-3 (Arc Consistency Algorithm 3) for constraint propagation
  - Backtracking Search with Forward Checking
  - MRV (Minimum Remaining Values) heuristic for variable selection
"""

import copy
import sys
from collections import deque


# ─────────────────────────────────────────────
#  GLOBAL STATS  (reset per puzzle)
# ─────────────────────────────────────────────
backtrack_calls   = 0   # how many times BACKTRACK was entered
backtrack_failures = 0  # how many times BACKTRACK returned failure


# ══════════════════════════════════════════════
#  SECTION 1 — CSP REPRESENTATION
# ══════════════════════════════════════════════

def build_csp(grid):
    """
    Convert a 9×9 Sudoku grid into a CSP.

    Parameters
    ----------
    grid : list[list[int]]
        9×9 grid where 0 = empty cell.

    Returns
    -------
    domains : dict  { (row, col) -> set of ints }
        For prefilled cells the domain is a singleton {digit}.
        For empty cells the domain starts as {1..9}.

    neighbors : dict  { (row, col) -> set of (row, col) }
        Every cell's set of peers (same row, col, or 3×3 box)
        that share an "all-different" constraint with it.
    """

    # --- Build domains ---
    domains = {}
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                domains[(r, c)] = {grid[r][c]}      # already fixed
            else:
                domains[(r, c)] = set(range(1, 10))  # could be anything

    # --- Build neighbor sets ---
    neighbors = {cell: set() for cell in domains}

    for r in range(9):
        for c in range(9):
            peers = set()

            # Same row
            for cc in range(9):
                if cc != c:
                    peers.add((r, cc))

            # Same column
            for rr in range(9):
                if rr != r:
                    peers.add((rr, c))

            # Same 3×3 box
            box_r, box_c = 3 * (r // 3), 3 * (c // 3)
            for rr in range(box_r, box_r + 3):
                for cc in range(box_c, box_c + 3):
                    if (rr, cc) != (r, c):
                        peers.add((rr, cc))

            neighbors[(r, c)] = peers

    return domains, neighbors


# ══════════════════════════════════════════════
#  SECTION 2 — AC-3
# ══════════════════════════════════════════════

def ac3(domains, neighbors):
    """
    AC-3: Arc Consistency Algorithm 3.

    Repeatedly enforces arc consistency across all constraint arcs.
    An arc (Xi, Xj) is consistent if for every value in Xi's domain
    there exists at least one compatible value in Xj's domain.

    For Sudoku the constraint is simply Xi ≠ Xj, so:
      → if Xj has only ONE value v, we can remove v from Xi's domain.
