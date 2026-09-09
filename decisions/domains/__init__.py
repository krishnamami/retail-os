"""Domain packs. The generic platform never imports from this subtree.

A domain pack supplies: predicates, rule bindings with their rule_class, a
canonical lookup adapter, and any domain-specific serialization. It is
constructed by the caller and injected into the executor.

Empty in D.4C by design (section 18: no Claris business predicates).
"""
