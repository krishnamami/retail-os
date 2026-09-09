"""Claris predicates.

D.4E implements the IDENTITY_ASSESSMENT pack: IR-011, IR-012, IR-013, IR-010,
in identity_assessment.py.

The four 0-byte placeholders at the repository root
(decisions/change_classification.py, decisions/identity_assessment.py,
decisions/launch_readiness.py) are still NOT moved here. D.4C recorded that as
deviation R-3 because the phase brief did not instruct a move, and the D.4E
brief does not either. Moving a root module is a placement change that touches
generic package layout, so it stays a deliberate decision for a later phase
rather than a side effect of this one.
"""

from __future__ import annotations

from .identity_assessment import (
    IDENTITY_PREDICATES,
    IR_010,
    IR_011,
    IR_012,
    IR_013,
    ir_010_exact_identity_match,
    ir_011_missing_required_input,
    ir_012_contradicted_required_input,
    ir_013_initial_configuration,
)

__all__ = [
    "IR_010",
    "IR_011",
    "IR_012",
    "IR_013",
    "ir_010_exact_identity_match",
    "ir_011_missing_required_input",
    "ir_012_contradicted_required_input",
    "ir_013_initial_configuration",
    "IDENTITY_PREDICATES",
]
