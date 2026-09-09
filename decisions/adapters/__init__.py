"""Live read-only adapters for the governed decision runtime.

Infrastructure, not domain. These modules translate real governed storage into
D.4C contracts and know nothing about any decision type.

    connection.py     read-only PostgreSQL boundary (Secrets Manager pattern)
    fold_postgres.py  state.fold_state_snapshot -> FoldSnapshotView
    kb_postgres.py    claris_kb governance metadata -> ResolvedRuleSet

Every statement is gated to SELECT/WITH and the session is pinned READ ONLY.
"""
