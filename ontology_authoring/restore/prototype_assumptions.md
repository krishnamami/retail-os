# Prototype governance assumptions -- 2026.10-prototype.1

**PROTOTYPE. NOT CLARIS APPROVED. FOR DEMONSTRATION ONLY.**

Validation status: `TO_BE_VALIDATED_WITH_CLARIS`

Parent authoritative release: `2026.10`

Every value below is an engineering assumption. None is confirmed governance. No authority, signature or evidence is claimed for any of them, and none may be presented to anyone as a Claris decision.

## Locked identity tuple

```
product_reference | geography | term_months | customer_segment
```

Serialization order is the order above. Membership is a **prototype assumption**, not Claris-confirmed canonical identity.

## Dimensions

| Dimension | In tuple | Assumed identity-bearing | Note |
|---|---|---|---|
| `product_reference` | yes | yes | PROTOTYPE ASSUMPTION. Prototype-only: 2026.10 has no counterpart. Q-007 asks whether any identifier spans the process, or identity starts at the material number. |
| `geography` | yes | yes | PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'geo' dimension, which is UNKNOWN and unsigned there. 63 materials from geo additions, none replacing an existing material. |
| `term_months` | yes | yes | PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'term' dimension, which is UNKNOWN and unsigned there. Q-009 asks whether term months and contract length months are the same business concept. |
| `customer_segment` | yes | yes | PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'segment' dimension, which is UNKNOWN and unsigned there. |
| `user_tier` | no | no | PROTOTYPE ASSUMPTION -- THE MOST CONSEQUENTIAL ONE IN THIS RELEASE. Assumed NOT identity-bearing, which is what makes IR-005 conclude NEW_VERSION and what avoids 78 of the 92 replacement materials in the corpus. If Claris says user tier IS identity-bearing, IR-005 becomes CREATE_CONFIGURATION and that saving does not exist. Unvalidated. |
| `package_format` | no | no | PROTOTYPE ASSUMPTION WITH A RECORDED CONFLICT. 2026.10 proposes this dimension IS identity-bearing (IR-006 -> CREATE_CONFIGURATION), but the locked prototype identity tuple excludes it, so this release assumes NOT identity-bearing in order to keep the tuple at four properties. The two assumptions disagree: under this release a repackage yields an identical canonical identity and the exact-match predicate concludes NO_BUSINESS_CHANGE, so the CREATE_CONFIGURATION that IR-006 proposes is unreachable. Recorded, not resolved: resolving it means changing tuple membership, which G.5P locked. |
| `description` | no | no | PROTOTYPE ASSUMPTION. Assumed not identity-bearing, matching 2026.10's own proposal. 2026.10 marks it CONFIRMED but with no confirmed_by or confirmed_on, so it is unsigned there and unconfirmed here. |

## Change assumptions

| Rule | Change | Reads | Assumed effect | Classification |
|---|---|---|---|---|
| `IR-001` | `new_product_family` | `-` | `CREATE_PRODUCT` | **SAFE FOR PROTOTYPE** |
| `IR-002` | `geo_add` | `geography` | `CREATE_CONFIGURATION` | **ASSUMPTION -- LABEL** |
| `IR-003` | `term_add` | `term_months` | `CREATE_CONFIGURATION` | **ASSUMPTION -- LABEL** |
| `IR-004` | `segment_add` | `customer_segment` | `CREATE_CONFIGURATION` | **ASSUMPTION -- LABEL** |
| `IR-005` | `tier_restructure` | `user_tier` | `NEW_VERSION` | **ASSUMPTION -- PROMINENT LABEL** |
| `IR-006` | `repackage` | `package_format` | `None` | **BLOCKED EVEN FOR PROTOTYPE** |
| `IR-008` | `price_change` | `-` | `NEW_VERSION` | **SAFE FOR PROTOTYPE** |
| `IR-009` | `rename` | `description` | `NO_BUSINESS_CHANGE` | **SAFE FOR PROTOTYPE** |

## Excluded

| Rule | Change | Classification | Why |
|---|---|---|---|
| `IR-007` | `reclassify` | **BLOCKED EVEN FOR PROTOTYPE** | 2026.10 states: NO PROPOSAL POSSIBLE. No definition of SLP exists anywhere in the process documentation. Its proposed effect rests on an inference from position in the process, not on knowledge. Executing it would demonstrate a conclusion about a term we cannot define. A reclassify change must reach CANNOT_DECIDE / IDENTITY_POLICY_NOT_DEFINED instead. |

## Executable predicates

| ID | Predicate | Class | Precedence | Concludes |
|---|---|---|---|---|
| `IA-PRED-001` | `ir_011_missing_required_input` | GUARD | 1 | `CANNOT_DECIDE` |
| `IA-PRED-002` | `ir_012_contradicted_required_input` | GUARD | 2 | `CANNOT_DECIDE` |
| `IA-PRED-003` | `ir_013_initial_configuration` | MATCH | 5 | `CREATE_CONFIGURATION` |
| `IA-PRED-004` | `ir_010_exact_identity_match` | MATCH | 6 | `NO_BUSINESS_CHANGE` |

No FALLBACK is declared. D.4B locked none, and inventing one would give the decision a terminal outcome no authority sanctioned.

## Recorded conflicts -- not resolved here

- **`IR-006` repackage is not reachable under the locked tuple.** `package_format` is excluded from the four identity properties, so a repackage produces an identical canonical identity and `IA-PRED-004` concludes `NO_BUSINESS_CHANGE` before `IR-006` is considered. Resolving this means changing tuple membership, which G.5P locked. Escalated.
- **`IR-005` tier_restructure carries the release's largest unvalidated claim.** 78 of 92 replacement materials turn on it.

## Row counts

| Table | Rows |
|---|---|
| `actors` | 7 |
| `configuration_dimensions` | 7 |
| `decision_outputs` | 6 |
| `decision_rule_bindings` | 4 |
| `decisions` | 1 |
| `identity_rules` | 8 |
| `ontology_release` | 1 |
| **total** | **34** |
