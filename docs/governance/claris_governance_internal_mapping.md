# INTERNAL — NOT FOR CLARIS
# Claris Governance Question Set — Traceability and Mapping

Phase: D.4G.1H.2 (question IDs corrected at D.4G.1G.4)
Status: PREPARED. No business answer recorded. Q-001 and Q-002 open.

> This document is **internal**. None of it is shown to Claris stakeholders.
> It contains technical defects, evidence gaps and construct mappings that are
> engineering's responsibility and must never be routed to a business
> stakeholder.
>
> Nothing in this document converts a candidate into confirmed governance.
> Every mapping below is **pending business confirmation**.

---

## 1. Question register

| ID | Subject | In stakeholder material | Status |
|---|---|---|---|
| Q-001 | SLP meaning, classification, identity effect, ownership | session section 3 | **OPEN — unanswered** |
| Q-002 | Canonical identity characteristics | session section 4 | **OPEN — unanswered** |
| Q-008 | Product / Configuration / Version boundaries | session section 1 | prepared |
| Q-003 | Downstream identifiers vs business offering | session section 2 | prepared |
| Q-007 | Product reference meaning | folded into section 4 clarification | prepared |
| Q-009 | Contract term equivalence | folded into section 4 clarification | prepared |
| Q-010 | Outcome-state sufficiency | session section 5 | prepared |
| Q-011 | Launch-readiness relationship | session section 6 | prepared |
| Q-012 | Business authority, 10 areas | written follow-up (appendix) | prepared |

**ID collision — RESOLVED at D.4G.1G.3, applied at D.4G.1G.4.** The repository
ontology notes were read in full. Two provisional IDs duplicated existing open
questions and have been re-pointed rather than renumbered: the downstream-identifier
question is the existing **Q-003** (`legacy_update_in_place`), and the product-reference
question is the existing **Q-007** (`join_key`). Both keep their original governance
subject and their existing owners; only the asked wording is the improved D.4G.1H
phrasing. The remaining provisional IDs were shifted down into free slots:
Q-009 to Q-003, Q-010 to Q-007, Q-011 to Q-009, Q-012 to Q-010. Q-008 is unchanged.
Q-001 and Q-002 are untouched. No ID is now used twice.

The product-reference and contract-term clarifications keep their own IDs
(Q-007 and Q-003) for traceability even though stakeholders encounter them as
clarifications inside Q-002 rather than as separate topics. Q-002 row 04
(reference ID) is a sub-part of Q-007 and is answered with it.

---

## 2. Q-002 — full 15-characteristic register

All fifteen candidates are retained. Ten are primary; four are follow-up; SLP is
asked once under Q-001.

| # | Characteristic | Classification | Evidence status | Governed construct affected | What an answer unblocks |
|---|---|---|---|---|---|
| 1 | Product family | PRIMARY | identity-affecting in 2 of 3 evidenced tuples; present in all 4 projection rules | identity_affecting (Question A) | identity tuple |
| 2 | Offering | PRIMARY | identity-affecting in 2 of 3 evidenced tuples | identity_affecting | identity tuple |
| 3 | Product reference | PRIMARY | **prototype only** — no counterpart in any inspected authoring model | identity_affecting; prototype-to-characteristic mapping | identity tuple + mapping |
| 4 | Reference ID | PRIMARY | referenced by the live identity decision, **undefined** as a characteristic | identity_affecting; dangling-reference repair | identity tuple + repair |
| 5 | Geography | PRIMARY | identity-affecting in all 3 evidenced tuples | identity_affecting | identity tuple |
| 6 | Market | PRIMARY | identity-affecting in the authoring model, **absent from the prototype** | identity_affecting | identity tuple |
| 7 | Contract term | PRIMARY | **sharpest conflict in the corpus**: prototype treats it as identity-affecting; the live characteristic is explicitly flagged not identity-affecting; a third, differently-named term characteristic is required but undefined | identity_affecting; dangling-reference repair | identity tuple + repair |
| 8 | Customer segment | PRIMARY | identity-affecting in all 3 evidenced tuples | identity_affecting | identity tuple |
| 9 | Tier — product/edition | PRIMARY | identity-affecting in the authoring model, **absent from the prototype** | identity_affecting | identity tuple |
| 10 | Tier — licensed users/seats | PRIMARY | **terminology collision only** — no distinct counterpart anywhere | identity_affecting; whether the characteristic exists | identity tuple |
| 11 | Currency | FOLLOW-UP | characteristic exists, recorded as not identity-affecting — **but the recorded value may be an unexamined default rather than a decision** | identity_affecting | matrix completeness |
| 12 | Price | FOLLOW-UP | same caveat as currency | identity_affecting | matrix completeness |
| 13 | Package / packaging format | FOLLOW-UP | **evidenced at 2026.10** as a governed dimension (`package_format`), `identity_affecting = UNKNOWN`, 12 observed materials all replacing an existing one, rule IR-006 proposes CREATE_CONFIGURATION | identity_affecting | matrix completeness |
| 14 | Description / name | FOLLOW-UP | **evidenced at 2026.10** as a governed dimension (`description`), the only one carrying `identity_affecting = FALSE` / `CONFIRMED`; rule IR-009 proposes NO_BUSINESS_CHANGE. **But `confirmed_by` and `confirmed_on` are NULL on both — the confirmation is unsigned and is NOT authoritative** | identity_affecting; re-confirmation of an unsigned row | matrix completeness |
| 15 | SLP | ASKED UNDER Q-001 | **no counterpart anywhere** | identity_affecting; whether the characteristic exists | Q-001 |

### Selection rule for PRIMARY

The ten primary rows are those where the evidenced sources **disagree with each
other** (rows 3, 4, 6, 7, 9, 10), plus the four they agree on but which have
never been confirmed by the business (rows 1, 2, 5, 8).

Rows 11 and 12 are not disputed by any source. Rows 13 and 14 **are** evidenced at 2026.10 and were wrongly described as unevidenced in
D.4G.1H; corrected at D.4G.1G.5. They stay in follow-up because the selection rule was
*disputed first*, and neither is disputed across sources: `package_format` sits at UNKNOWN
like five of its siblings, and `description` is the single dimension anyone has proposed an
answer for. Neither may be presented to Claris as settled — `description`'s CONFIRMED state
carries no signature, so it is a proposal wearing a confirmation's label, and Claris is asked
to confirm it rather than to review it.

---

## 3. Question to construct mapping

| Q | Governed construct | Decision affected | Candidate rule / characteristic | Current uncertainty | What an answer unblocks |
|---|---|---|---|---|---|
| Q-008 | object model; identity-effect vocabulary | IDENTITY_ASSESSMENT, CHANGE_CLASSIFICATION | initial-configuration rule | the three-level model is inherited, never business-confirmed | separability of new-product from new-configuration; the initial-configuration trigger |
| Q-003 | proliferation classification | LEGACY_PROJECTION_REQUIREMENT | all 4 projection rules, **all** asserting "business required" with no recorded basis; the classification's other two values are unused | whether physical identifiers ever drive canonical identity | the proliferation objective; whether system identifiers are excluded from identity |
| Q-001 | identity_affecting; authority | IDENTITY_ASSESSMENT | matrix row 15 | **SLP appears in no inspected model** | whether SLP is a governed characteristic at all |
| Q-002 | identity_affecting x15; canonical identity tuple; identity rule composition | IDENTITY_ASSESSMENT | exact-match rule, initial-configuration rule | **four-way divergence** across evidenced representations (6 / 6 / 8 / 4 characteristics); the live identity flag carries a false default that may assert what nobody decided | the identity tuple — which in turn unblocks the identity serializer, exact-match semantics, and the prototype's correctness |
| Q-007 | prototype-to-characteristic mapping | IDENTITY_ASSESSMENT | product reference | the prototype tuple uses no authoring-model characteristic identifier at all | the mapping; matrix rows 1-4 |
| Q-009 | as row 7 | IDENTITY_ASSESSMENT | term | rename, duplicate or genuinely distinct — unknown | dangling-reference repair; matrix row 7 |
| Q-010 | identity-effect outcome vocabulary; decision reason codes | IDENTITY_ASSESSMENT | future outcome set | the six states are inherited and never business-confirmed | vocabulary completeness; whether a governed refusal-to-decide is wanted |
| Q-011 | relationship between identity assessment and launch readiness | both | the legacy launch-readiness outcome and its **7 live dependents** | the legacy model places a launch-readiness value in the identity outcome slot; whether that is a modelling accident or a business truth is unknown | whether the two vocabularies coexist by version, additively |
| Q-012 | authority; confirmation fields | all | — | ownership was dropped from all 108 re-authored records; authority is currently unrecoverable | the authority field on every confirmation record |

**Minimum sufficient set to unblock a governed IDENTITY_ASSESSMENT:**
Q-002, with Q-007, Q-009 and Q-001 as prerequisites, plus Q-010.
Q-008, Q-003, Q-011 and Q-012 are required for a complete governance model but
do not individually block the identity decision.

---

## 4. Outcome-state mapping — PENDING BUSINESS CONFIRMATION

Presented to stakeholders in business language only. No internal name appears in
the stakeholder material. This mapping is applied **only after** Q-010.a confirms
the six states are sufficient.

| Business state (session section 5) | Internal — PENDING CONFIRMATION |
|---|---|
| A. Create a completely new product family | `CREATE_PRODUCT` |
| B. Create another sellable configuration under an existing product | `CREATE_CONFIGURATION` |
| C. Reuse a sellable configuration that already exists | `USE_EXISTING` |
| D. Create a new governed version without changing sellable identity | `NEW_VERSION` |
| E. Record the change, no product/configuration identity change | `NO_BUSINESS_CHANGE` |
| F. Make no automated determination | `CANNOT_DECIDE` |

**The legacy launch-readiness outcome is not mapped to any of these**, and no
equivalence is proposed or implied. Q-011 tests whether the two are separate
business judgments; it does not ask whether one equals the other.

---

## 5. Dependency ordering

| # | Question | Depends on | Reason |
|---|---|---|---|
| 1 | Q-008 | — | establishes the vocabulary everything else uses |
| 2 | Q-003 | Q-008 | **must precede Q-002** |
| 3 | Q-001 | Q-008 | matrix row 15 is unanswerable until SLP has a meaning |
| 4 | Q-002 (+ Q-007, Q-009) | Q-008, Q-003, Q-001 | the primary question |
| 5 | Q-010 | Q-008, Q-002 | outcomes presuppose the object model |
| 6 | Q-011 | Q-010 | separation question presupposes the outcome set |
| 7 | Q-012 | all | written follow-up |

**Why Q-003 precedes Q-002.** SKU history is the concrete, retrievable evidence
in front of stakeholders; business identity is the abstraction. If the matrix is
reached before the two have been explicitly separated, every YES risks being an
artifact of a downstream system constraint, with no way afterwards to tell which
rows were affected. Six minutes spent first protects the primary question.

---

## 6. Evidence gaps — disclosed internally, never raised as facts with Claris

- **Package / packaging format** and **description / name** were recorded here as
  having no counterpart. That was wrong, and is corrected: both are governed
  dimensions at 2026.10 (`package_format`, `description`), with rules IR-006 and
  IR-009 respectively. The error came from working off carried summaries instead of
  the source.
- **`description` is marked CONFIRMED at 2026.10 with `confirmed_by` and
  `confirmed_on` both NULL**, as is IR-009. An unsigned confirmation is not a
  confirmation; both restore as proposed and both still need Claris.
- **SLP** appears in no inspected model — not as a characteristic, not as a
  column, not as a value.
- **Q-003 through Q-007** in the repository ontology notes have not been read.
- The live identity flag is a two-valued field with a false default, so a
  recorded "not identity-affecting" cannot be distinguished from "nobody ever
  decided". Every recorded value of that flag is therefore untrustworthy in both
  directions.

---

## 7. Known technical defects — engineering's, never Claris's

Carried, not raised in the session, not repaired in this phase:

- geography is typed too narrowly to hold two of its own three documented
  example values
- a dangling action reference on the legacy identity outcome
- inconsistent typing of the decision-input references
- 13 of 25 declared outcomes are not materialized in the outcome registry
- 2 foreign keys across 15 tables
- the policy-version registry is empty while 13 records reference a policy
  version, with no referential link
- unescaped delimiter collision in both the live identity expression and the
  prototype serializer
- outcome validation is not version-scoped
- the decision digest column is too narrow for the digest format in use
- missing fold-state and matched-rule columns on the decision record
- fail-closed active-release singleton is fragile

**None of these is a Claris question.** They belong to D.4G.1G.3 and D.4G.2.

---

## 8. Facilitator notes

- **Ask for examples before rules.** If a stakeholder stalls on Q-008.a or
  Q-008.b, ask for a recent case rather than a principle. The rule usually falls
  out of the third example.
- **Record DEPENDS conditions verbatim.** "Depends on the region" and "depends
  on whether the region has its own legal entity" are different rules.
- **Do not translate into technical language in the room.** Not on the
  whiteboard, not in the notes. Translation happens afterwards, deliberately,
  against the recorded words.
- **Watch for SKU reasoning contaminating the matrix.** If someone answers a row
  with "yes, because we had to make a new SKU", that is a Q-003 answer, not a
  Q-002 answer. Say so and ask the business question again.
- **Blank is a legitimate outcome.** Do not fill a row to be tidy. Do not accept
  "I suppose not" as a NO — that is a blank.
- **Do not offer candidates.** If Q-008.b stalls, the prompts *price change,
  rename, entitlement adjustment, packaging adjustment, term change* exist as a
  last resort only. Offering them unprompted turns an open question into a
  confirmation exercise.
- **Do not push toward an answer, and do not manufacture consensus.**
- **Do not defend the current system.** If a stakeholder says something
  contradicts how things work today, record the contradiction and move on.
- **The person speaking is not automatically the authority.** If someone
  volunteers a function for Q-012, record it as an observation, not as the
  answer.
- **Capture who could resolve a disagreement**, even where nobody present knows.
- **Use the buffer for discussion, not for more questions.** The question set is
  closed; the 13-minute buffer exists for examples, disagreement and unresolved
  items.

---

## 9. Disagreement contract

If two stakeholders give different answers, **do not choose between them and do
not seek consensus in the room.**

- record each answer as its own **observation**, with person, function,
  reasoning and examples
- set `answer_status: DISAGREEMENT`
- leave `resolved_answer` **blank**
- record `authority` separately — and if nobody present knows who that is,
  record that too

The question stays unresolved until the accountable function resolves it.

A disagreement recorded honestly is a better input than an agreement
manufactured under time pressure: it tells us the policy genuinely is not
settled, which is itself a governance finding. **A disagreement is governance
evidence. It is not a failed meeting.**

The same observation structure handles the ordinary single-answer case, so there
is no separate path for it.

---

## 10. What must never be asked of Claris

Not asked, in any form, in any question: which schema is authoritative; the
relationship between the authoring and artifact layers; artifact storage;
compiler architecture; version encoding; identity serialization, delimiters or
hashing; projection storage; database roles or grants; runtime defects; rule
identifiers; internal outcome names; migrations; or whether our model or
implementation is correct.

Those are engineering responsibilities. Nothing in the technical-defect list in
section 7 is routed to a business stakeholder.
