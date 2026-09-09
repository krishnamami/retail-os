"""Decision persistence boundary. Empty in D.4C by design.

The executor returns a value and writes nothing. DecisionWriter
(DecisionResult -> claris.decision + lineage, in one transaction) is a later
phase, as is decision_logger.py.
"""
