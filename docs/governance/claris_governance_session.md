# Claris — Product & Configuration Governance
## Working session

**Calendar:** 60 minutes — approximately 45 minutes of core questions, the rest
for examples, discussion and anything that needs unpicking.

**Status:** PREPARED — NOT YET SENT.

---

<!-- ADVANCE MATERIAL BEGINS: the purpose, the working definitions and the
     characteristic labels in question 4 may be shared before the session so
     people can think. Answers are collected live. Nothing is pre-filled. -->

## Why we are meeting

We are defining how Claris should tell a genuinely different product or sellable
configuration apart from a change that is only a version, a pricing or
entitlement variation, or something a downstream system required.

The goal of this session is to confirm which business rules we should automate,
and who owns those rules.

**If something isn't settled today, leaving it blank is better than guessing.**
A blank tells us to come back to it. A guess gets built into a system.

## Working definitions

These are our starting point, not decisions. Please correct them.

- **Product** — a product family or offering the business thinks of as a single
  thing it sells.
- **Configuration** — a distinct sellable configuration of that product: a
  specific combination of characteristics the business treats as its own
  sellable thing.
- **Version** — a governed change to an existing configuration that does not
  make it a different sellable thing. It keeps its identity; the change is
  tracked.
- **Legacy SKU / material** — an identifier required by a downstream system
  (SAP, FileMaker, all_skus, catalog). *Whether a new SKU or material means a
  new configuration is one of the things we want to understand — question 2
  covers it.*
- **Identity-affecting characteristic** — a characteristic where changing its
  value means the business considers the result a different sellable
  configuration.

<!-- ADVANCE MATERIAL: also shareable in advance are the characteristic labels
     listed in the question 4 table. Do not share the answer columns filled in. -->

## Agenda

| | | Approx. |
|---|---|---|
| | Purpose and working definitions | 5 min |
| 1 | Product, Configuration, Version — where are the boundaries? | 8 min |
| 2 | Downstream system identifiers and the business offering | 6 min |
| 3 | SLP | 5 min |
| 4 | What makes one sellable configuration different from another? | 14 min |
| 5 | Are these the outcomes you need? | 6 min |
| 6 | "Ready to launch" and identity | 3 min |
| | Buffer — examples, discussion, anything unresolved | 13 min |

A short written follow-up on **who owns each of these policies** is sent
separately. We are deliberately not asking that one under time pressure.

---

## 1. Product, Configuration, Version — where are the boundaries?

**1a.** What makes something a completely **new product**, rather than another
configuration of an existing product? *Two or three real examples from the last
year would help more than a rule.*

**1b.** What kinds of changes keep the **same** configuration but create a
**new version** of it? Again — examples.

**1c.** Do the working definitions above match how Claris actually talks about
these? If not, how would you put it?

---

## 2. Downstream system identifiers and the business offering

**2a.** Are there situations where SAP, FileMaker or all_skus required a **new
SKU or material** even though the business considered it the **same offering**?
Examples?

**2b.** In those cases, what was it about the system that forced the extra
identifier?

**2c.** And the other way round — are there cases where the business considers
something a **different** offering, but no new SKU or material was created?

---

## 3. SLP  *(Q-001)*

**3a.** What does **SLP** represent in the product or SKU lifecycle?

**3b.** Is it best described as a product or configuration characteristic; a
classification used by a downstream system; a pricing characteristic; an
operational routing or classification; or something else?

**3c.** If **only** the SLP changes and the underlying commercial offering stays
the same, should the business treat the result as:

- the same configuration
- a new version of it
- a different configuration
- it depends — *on what?*

**3d.** Which business function owns the policy for SLP?

---

## 4. What makes one sellable configuration different from another?  *(Q-002)*

**For each characteristic: when this value changes and everything else stays the
same, does Claris consider the result a different sellable configuration?**

**YES · NO · DEPENDS · NOT APPLICABLE · NEEDS CLARIFICATION**

> **A blank row means "not answered yet" — and that is a perfectly good answer.**
> Please leave a row blank rather than guessing. We treat a blank very
> differently from a "no", and we would rather come back to it than record
> something nobody decided.

| # | Characteristic | What it means to you | Different configuration? | If YES: always, or only when...? |
|---|---|---|---|---|
| 1 | Product family | | | |
| 2 | Offering | | | |
| 3 | Product reference *(see below)* | | | |
| 4 | Reference ID *(see below)* | | | |
| 5 | Geography | | | |
| 6 | Market | | | |
| 7 | Contract term *(see below)* | | | |
| 8 | Customer segment | | | |
| 9 | Tier — product/edition *(Premium / Standard / Basic)* | | | |
| 10 | Tier — licensed users or seats | | | |
| — | *SLP* | | *answered in question 3c* | |

### Three things we need to get straight as we go

**Product reference and reference ID.** We have seen both terms and we are not
confident what either means to you. Are they the same thing, two different
things, or terms you don't actually use? And is a "reference" the name for a
product the business already defined some other way — or does changing it mean
the product itself is different?

**Contract term.** We have seen both *term months* and *contract length months*.
Same thing, or different? If different, what is the distinction?

**Tier.** We have seen "tier" used for a product or edition tier
(Premium / Standard / Basic) and, separately, for a licensed-user or seat band.
Are these one characteristic or two? If we have got that wrong, tell us and
answer just the one row that applies.

### Two more points on the table above

**Rows 5 and 6.** We see geography and market used as two different things. Is
that right, and what does each mean — country, region, sales territory, legal
entity, industry, something else?

**Row 8.** What does segment cover? We have seen enterprise, education,
nonprofit, retail — we do not assume that is the right or complete list.

### 4d. Completeness

Thinking about the changes you actually handle — new product, new geography, new
term, new segment, tier change, repackage, SLP reclassification, price change,
rename — is anything **missing** from the list above? Anything you would
**combine**, or **split**, differently?

### Follow-up characteristics

These are **follow-up candidates**, not established Claris characteristics. We
raise them only if time allows, and otherwise in writing afterwards.

| # | Characteristic | Different configuration? | The question, when we get to it |
|---|---|---|---|
| 11 | Currency (the money it is sold in) | | Same offering sold in another currency — same configuration with different pricing, or a different configuration? |
| 12 | Price | | If only the price changes and nothing else — a version, or no identity change at all? |
| 13 | Package / packaging format | | First: what does packaging format mean in Claris terms? *Please answer from the business, not from whether a new SKU was created — question 2 covers that.* |
| 14 | Description or name only | | If only the customer-facing or internal name changes, and no commercial terms or capabilities change — new version, no identity change, different configuration, or depends? |

Any row above in the primary table left blank during the session also becomes a
follow-up. A blank is never read as a "no".

---

## 5. Are these the outcomes you need?

When a change comes in, we want the system to reach exactly one of these
conclusions:

- **A.** Create a completely new product family.
- **B.** Create another sellable configuration under an existing product.
- **C.** Reuse a sellable configuration that already exists.
- **D.** Create a new governed version of an existing configuration, without
  changing what it is as a sellable thing.
- **E.** Record the change, but nothing about the product or configuration
  identity changes.
- **F.** Make no automated determination — the policy or evidence needed is
  missing or contradictory, and a person decides.

**5a.** Are these six enough to describe the outcomes Claris needs?

**5b.** If not, what business situation is missing?

**5c.** When the system doesn't have what it needs, is **F** what you would
expect it to do — or something else?

---

## 6. "Ready to launch" and identity

**6a.** Deciding *"what business object does this change represent?"* and
deciding *"is that object ready to proceed through launch?"* — are these one
judgment or two?

**6b.** If two, does one need to happen before the other?

---

## Appendix — sent separately: who owns these policies?  *(Q-012)*

Not part of the live session. For each area, who is accountable for the final
business decision?

Any of these is a valid answer: **one accountable function**, **joint
approval**, **varies by circumstance**, or **unknown**.

| Policy area | Accountable for the final decision |
|---|---|
| Product identity | |
| Configuration identity | |
| SLP | |
| Pricing | |
| Customer segment | |
| User tier / entitlement | |
| Geography / market | |
| Package format, if applicable | |
| Launch readiness | |
| Projection into downstream systems | |
