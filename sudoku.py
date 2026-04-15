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

    Parameters
    ----------
    domains   : dict (modified IN-PLACE)
    neighbors : dict

    Returns
    -------
    True  – domains are arc-consistent (may have been pruned)
    False – a domain was wiped out → puzzle is unsolvable from here
    """

    # Initialise queue with every arc in both directions
    queue = deque()
    for xi in domains:
        for xj in neighbors[xi]:
            queue.append((xi, xj))

    while queue:
        xi, xj = queue.popleft()

        if revise(domains, xi, xj):
            # xi's domain was pruned
            if len(domains[xi]) == 0:
                return False   # domain wiped out → contradiction

            # Re-add all arcs pointing INTO xi (their consistency may be broken)
            for xk in neighbors[xi]:
                if xk != xj:
                    queue.append((xk, xi))

    return True


def revise(domains, xi, xj):
    """
    Make arc (Xi → Xj) consistent by removing values from Xi's domain
    that have no support in Xj's domain.

    For Sudoku (Xi ≠ Xj):
      A value v in Xi has NO support only when Xj's domain = {v}
      (the only option for Xj is exactly v, so Xi can't be v).

    Returns True if we removed anything, False otherwise.
    """
    revised = False

    # Iterate over a snapshot so we can safely remove during iteration
    for v in set(domains[xi]):
        # v is supported if there is at least one w in Xj with w ≠ v
        if not any(w != v for w in domains[xj]):
            domains[xi].discard(v)
            revised = True

    return revised


# ══════════════════════════════════════════════
#  SECTION 3 — BACKTRACKING SEARCH
# ══════════════════════════════════════════════

def select_unassigned_variable(domains, assignment):
    """
    MRV Heuristic — Minimum Remaining Values.

    Pick the unassigned variable whose domain is smallest.
    Cells with fewer options are more likely to cause failures early,
    so we tackle them first (fail-fast strategy).
    """
    unassigned = [cell for cell in domains if cell not in assignment]
    # Sort by domain size; pick the smallest
    return min(unassigned, key=lambda cell: len(domains[cell]))


def forward_check(domains, neighbors, var, value):
    """
    Forward Checking: after assigning `value` to `var`,
    remove `value` from every unassigned neighbor's domain.

    Returns
    -------
    pruned : dict { cell -> set of removed values }
        Keeps track of what was removed so we can UNDO on backtrack.
    None   : if any neighbor's domain is wiped out (dead end detected).
    """
    pruned = {}   # { cell : {values removed from it} }

    for neighbor in neighbors[var]:
        if value in domains[neighbor]:
            domains[neighbor].discard(value)
            pruned.setdefault(neighbor, set()).add(value)

            if len(domains[neighbor]) == 0:
                # Dead end — undo what we just pruned before returning
                restore_domains(domains, pruned)
                return None   # signal failure

    return pruned


def restore_domains(domains, pruned):
    """
    Undo the pruning done by forward_check.
    Called whenever we backtrack.
    """
    for cell, values in pruned.items():
        domains[cell].update(values)


def backtrack(assignment, domains, neighbors):
    """
    Recursive Backtracking Search.

    Base case : all 81 cells assigned → return the solution.
    Recursive : pick the best unassigned variable (MRV),
                try each value in its domain,
                run forward checking,
                recurse.

    Global counters `backtrack_calls` and `backtrack_failures`
    are incremented here for analysis.
    """
    global backtrack_calls, backtrack_failures
    backtrack_calls += 1

    # ── Base case: complete assignment ──
    if len(assignment) == 81:
        return assignment

    # ── Choose variable ──
    var = select_unassigned_variable(domains, assignment)

    # ── Try each value in the domain ──
    for value in sorted(domains[var]):   # sorted for determinism

        # Assign
        assignment[var] = value
        original_domain = set(domains[var])
        domains[var] = {value}           # fix domain to chosen value

        # Forward check
        pruned = forward_check(domains, neighbors, var, value)

        if pruned is not None:
            # Forward check passed — recurse
            result = backtrack(assignment, domains, neighbors)

            if result is not None:
                return result            # ✓ solution found

        # ── Undo ──
        del assignment[var]
        domains[var] = original_domain  # restore domain
        if pruned is not None:
            restore_domains(domains, pruned)

    # All values exhausted — report failure
    backtrack_failures += 1
    return None


def solve(grid):
    """
    Full pipeline:
      1. Build CSP from grid
      2. Run AC-3 for initial propagation
      3. Run backtracking search

    Returns (solution_grid, calls, failures) or (None, calls, failures).
    """
    global backtrack_calls, backtrack_failures
    backtrack_calls   = 0
    backtrack_failures = 0

    domains, neighbors = build_csp(grid)

    # --- Initial AC-3 pass ---
    if not ac3(domains, neighbors):
        return None, backtrack_calls, backtrack_failures

    # --- Pre-assign cells already determined by AC-3 ---
    assignment = {}
    for cell, domain in domains.items():
        if len(domain) == 1:
            assignment[cell] = next(iter(domain))

    # --- If AC-3 alone solved it, we're done ---
    if len(assignment) == 81:
        return assignment_to_grid(assignment), backtrack_calls, backtrack_failures

    # --- Otherwise, backtrack ---
    result = backtrack(assignment, domains, neighbors)

    if result is None:
        return None, backtrack_calls, backtrack_failures

    return assignment_to_grid(result), backtrack_calls, backtrack_failures


# ══════════════════════════════════════════════
#  SECTION 4 — UTILITIES
# ══════════════════════════════════════════════
