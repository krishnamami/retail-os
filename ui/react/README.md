# Claris Common Decision Platform — demo frontend

A React demo over **governed state only**. Nothing in this app computes a
governed outcome: every READY / NOT_READY / CANNOT_DECIDE / NO_BUSINESS_CHANGE
it shows is read from a field the backend already decided.

## Run it

```bash
python workbench/collect.py     # from the repo root: writes out/workbench_data.json
cd ui/react
npm install
npm run dev                     # http://localhost:5174  (predev runs sync-data)
```

`npm run build` produces `dist/`, servable from any path (relative base +
hash routing). If `out/workbench_data.json` is absent, `sync-data` warns and
the app shows an explicit empty state rather than placeholder launches.

## Where data comes from

`scripts/sync-data.mjs` copies `out/workbench_data.json` into `public/data/`.
`src/data/source.ts` is the only file that knows where governed data lives —
replace the fetch there with an API call and no page component changes.

## The line the frontend does not cross

`src/data/model.ts` groups, labels and orders. It never derives a verdict.
The test: if the backend changed its mind, would this code still produce the
same answer? If yes, it is deriving an outcome and does not belong here.

## Not implemented, deliberately

No sign-in or IAM. No launch creation. No mail is sent. No write to SAP,
FileMaker, Salesforce or ww_pricing. No evidence is entered by hand.
