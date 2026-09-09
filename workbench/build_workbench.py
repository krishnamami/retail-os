r"""Builds the Common Decision Workbench as one self-contained HTML file.

    .\venv\Scripts\python.exe workbench\collect.py
    .\venv\Scripts\python.exe workbench\build_workbench.py

Reads out\workbench_data.json, embeds it, writes out\workbench.html. Open that
file directly in a browser -- no server, no network, no build step. The data is
embedded rather than fetched because a page opened from disk cannot fetch a
sibling file, and adding a server to a prototype would be the wrong kind of
work.

PRODUCT BOUNDARY, ENFORCED IN THE UI
    There is no New Launch and no Create Launch. Claris systems initiate
    launches and changes; this Workbench answers where an existing one stands.
    Every action it offers is a draft.
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
OUT = os.path.join(_ROOT, "out")

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claris Common Decision Workbench</title>
<style>
:root{
  --bg:#f7f7f5; --panel:#fff; --ink:#1a1a18; --muted:#6b6b66; --line:#e3e3de;
  --observed:#1f7a4d; --observed-bg:#e8f5ee;
  --defaulted:#9a5b00; --defaulted-bg:#fdf0dd;
  --unreported:#6b6b66; --unreported-bg:#eeeeea;
  --failed:#a32020; --failed-bg:#fbe9e9;
  --ready:#1f7a4d; --cannot:#9a5b00; --not-ready:#a32020;
  --accent:#2f5fd0;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#14140f; --panel:#1c1c18; --ink:#ecebe6; --muted:#9a9a92;
    --line:#2e2e28;
    --observed:#5fc48d; --observed-bg:#123122;
    --defaulted:#e5a860; --defaulted-bg:#33260f;
    --unreported:#9a9a92; --unreported-bg:#262621;
    --failed:#e88a8a; --failed-bg:#361b1b;
    --ready:#5fc48d; --cannot:#e5a860; --not-ready:#e88a8a;
    --accent:#7ba2f5;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0;font-size:17px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:12.5px;margin-top:4px}
.totals{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:12.5px}
.totals b{font-variant-numeric:tabular-nums}
main{display:grid;grid-template-columns:minmax(360px,1fr) minmax(0,1.6fr);
  gap:0;min-height:calc(100vh - 104px)}
@media(max-width:980px){main{grid-template-columns:1fr}}
.queue{border-right:1px solid var(--line);background:var(--panel);overflow:auto}
.queue h2,.detail h2{font-size:12px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);margin:16px 20px 8px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-weight:600;color:var(--muted);padding:7px 10px;
  border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--panel)}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr{cursor:pointer}
tbody tr:hover{background:var(--bg)}
tbody tr.sel{background:color-mix(in srgb,var(--accent) 10%,transparent);
  box-shadow:inset 3px 0 0 var(--accent)}
.detail{overflow:auto;padding-bottom:40px}
.tabs{display:flex;gap:2px;padding:0 20px;border-bottom:1px solid var(--line);
  flex-wrap:wrap;background:var(--panel);position:sticky;top:0;z-index:2}
.tab{padding:10px 12px;font-size:12.5px;color:var(--muted);cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap}
.tab.on{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
.pane{padding:18px 20px;display:none}.pane.on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:14px 16px;margin-bottom:12px}
.card h3{margin:0 0 2px;font-size:13.5px}
.card .intent{color:var(--muted);font-size:12px;margin-bottom:10px}
.outcome{font-weight:650;font-size:12.5px}
.READY{color:var(--ready)}.CANNOT_DECIDE{color:var(--cannot)}
.NOT_READY{color:var(--not-ready)}
.why{margin:8px 0 0;font-size:12.5px}
.chip{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;
  font-weight:600;letter-spacing:.02em}
.OBSERVED{background:var(--observed-bg);color:var(--observed)}
.DEFAULTED{background:var(--defaulted-bg);color:var(--defaulted)}
.UNREPORTED{background:var(--unreported-bg);color:var(--unreported)}
.FAILEDCHIP{background:var(--failed-bg);color:var(--failed)}
.kv{display:grid;grid-template-columns:200px 1fr;gap:4px 12px;font-size:12.5px}
.kv dt{color:var(--muted)}
.kv dd{margin:0}
.note{color:var(--muted);font-size:12px;margin-top:8px}
.journey{list-style:none;margin:0;padding:0}
.journey li{position:relative;padding:0 0 16px 22px;border-left:2px solid var(--line)}
.journey li:last-child{border-left-color:transparent}
.journey li::before{content:"";position:absolute;left:-6px;top:3px;width:10px;
  height:10px;border-radius:50%;background:var(--accent)}
.journey .stage{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 14px}
button{font:inherit;font-size:12.5px;padding:6px 11px;border-radius:6px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}
.draft{border:1px solid var(--line);border-radius:8px;padding:12px 14px;
  margin-bottom:10px;background:var(--panel)}
.draft pre{white-space:pre-wrap;font:12px/1.55 ui-monospace,Menlo,Consolas,monospace;
  margin:8px 0 0;color:var(--ink)}
.empty{color:var(--muted);font-size:12.5px;padding:10px 0}
.mono{font:12px ui-monospace,Menlo,Consolas,monospace}
.scroll{overflow-x:auto}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);
  margin:2px 20px 12px}
</style>
</head>
<body>
<header>
  <h1>Claris Common Decision Workbench</h1>
  <div class="sub">Where an existing launch or change stands, what is known,
    what is missing, and what is blocking it. Claris systems initiate launches;
    this does not.</div>
  <div class="totals" id="totals"></div>
</header>
<main>
  <section class="queue">
    <h2>Cases</h2>
    <div class="legend">
      <span><span class="chip OBSERVED">OBSERVED</span> a source asserted it</span>
      <span><span class="chip DEFAULTED">DEFAULTED</span> projection supplied it</span>
      <span><span class="chip UNREPORTED">UNREPORTED</span> nobody reported it</span>
    </div>
    <div class="scroll"><table id="queue">
      <thead><tr><th>Case</th><th>Domain</th><th>Decision state</th>
        <th>Waiting on</th><th>Primary blocker</th><th>Age</th>
        <th>Last activity</th></tr></thead>
      <tbody></tbody>
    </table></div>
  </section>
  <section class="detail">
    <div class="tabs" id="tabs"></div>
    <div id="panes"></div>
  </section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const TABS = ["Overview","Decision & Handoff Journey","Evidence",
              "Activity & Handoffs","Documents","Related"];
const IDENTITY_PROPS = ["product_reference","geography","term_months",
                        "customer_segment"];
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const days = iso => iso ? Math.max(0,Math.round(
  (Date.parse(DATA.horizon)-Date.parse(iso))/864e5)) : null;
const short = iso => iso ? String(iso).slice(0,10) : "—";

/* ---- cases: sku readiness cases, plus configuration-request identity cases */
function buildCases(){
  const cases = DATA.cases.map(c=>({
    kind:"sku", id:c.case.subject_id, domain:"Activation / Launch Readiness",
    state:(c.case.readiness.find(r=>r.decision_type==="LAUNCH_READINESS")||{}).outcome,
    waiting:(c.waiting_on&&c.waiting_on.role)||"—",
    blocker:c.blockers.length?c.blockers[0].kind:"—",
    first:c.case.first_activity, last:c.case.last_activity, agent:c
  }));
  const reqs = DATA.properties.configuration_request||{};
  for(const id of Object.keys(reqs).sort()){
    const decs = DATA.decisions.filter(d=>d.subject_id===id);
    const current = decs.find(d=>d.state==="current")||decs[decs.length-1];
    const props = reqs[id];
    const stamps = Object.values(props).map(p=>p.arrival_at).filter(Boolean);
    const missing = IDENTITY_PROPS.filter(
      p=>!props[p]||props[p].fold_state!=="ESTABLISHED");
    cases.push({
      kind:"configuration_request", id, domain:"Identity & Configuration",
      state:current?current.outcome_code:"NO_GOVERNED_DECISION",
      waiting:missing.length?"Requesting role":"—",
      blocker:missing.length?"ABSENT_EVIDENCE":"—",
      first:stamps.length?stamps.slice().sort()[0]:null,
      last:stamps.length?stamps.slice().sort().pop():null,
      props, decisions:decs, missing
    });
  }
  return cases;
}
const CASES = buildCases();

/* ---- header totals */
document.getElementById('totals').innerHTML = [
  `<span><b>${DATA.totals.evidence}</b> evidence</span>`,
  `<span><span class="chip OBSERVED">${DATA.totals.observed} observed</span></span>`,
  `<span><span class="chip DEFAULTED">${DATA.totals.defaulted} defaulted</span></span>`,
  `<span><b>${DATA.totals.mappings}</b> mappings</span>`,
  `<span><b>${DATA.totals.subjects}</b> subjects</span>`,
  `<span><b>${DATA.totals.property_states}</b> property states</span>`,
  `<span>horizon <span class="mono">${esc(DATA.horizon)}</span></span>`
].join("");

/* ---- queue */
const tbody = document.querySelector('#queue tbody');
tbody.innerHTML = CASES.map((c,i)=>`<tr data-i="${i}">
  <td><b>${esc(c.id)}</b></td><td>${esc(c.domain)}</td>
  <td class="${esc(c.state)}"><b>${esc(c.state)}</b></td>
  <td>${esc(c.waiting)}</td><td>${esc(c.blocker)}</td>
  <td>${c.first?days(c.first)+"d":"—"}</td><td>${short(c.last)}</td></tr>`).join("");

/* ---- tabs */
document.getElementById('tabs').innerHTML =
  TABS.map((t,i)=>`<div class="tab${i?"":" on"}" data-t="${i}">${t}</div>`).join("");
document.getElementById('panes').innerHTML =
  TABS.map((t,i)=>`<div class="pane${i?"":" on"}" id="p${i}"></div>`).join("");
document.getElementById('tabs').onclick = e => {
  const t = e.target.closest('.tab'); if(!t) return;
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
  t.classList.add('on');
  document.getElementById('p'+t.dataset.t).classList.add('on');
};

/* ---- render */
let CURRENT = null;
const localDrafts = {};

function provChip(p){
  if(!p) return `<span class="chip UNREPORTED">UNREPORTED</span>`;
  if(p.fold_state!=="ESTABLISHED") return `<span class="chip UNREPORTED">${esc(p.fold_state||"UNREPORTED")}</span>`;
  return `<span class="chip ${esc(p.provenance||"UNREPORTED")}">${esc(p.provenance||"—")}</span>`;
}

function readinessCard(v, c){
  const list = (label, items) => items && items.length
    ? `<dt>${label}</dt><dd>${items.map(esc).join(", ")}</dd>` : "";
  return `<div class="card">
    <h3>${esc(v.decision_type.replace(/_/g," "))}
      <span class="outcome ${esc(v.outcome)}">&nbsp;${esc(v.outcome)}</span></h3>
    <div class="intent">${esc(v.intent)}</div>
    <dl class="kv">
      <dt>why</dt><dd>${esc(v.why)}</dd>
      ${list("missing evidence", v.missing_evidence)}
      ${list("insufficient evidence", v.insufficient_evidence)}
      ${list("observed failure", v.failed)}
      <dt>policy</dt><dd class="mono">${esc(v.policy_version)}</dd>
    </dl>
    ${v.insufficient_evidence && v.insufficient_evidence.length ? `<p class="note">
      A value is present but no source asserted it. Confirming it is a decision
      someone must make, not a fact to look up.</p>`:""}
  </div>`;
}

function identityCard(c){
  const rows = IDENTITY_PROPS.map(p=>{
    const prop = c.props[p];
    return `<tr><td>${esc(p)}</td>
      <td>${prop&&prop.fold_state==="ESTABLISHED"?esc(prop.value):"—"}</td>
      <td>${provChip(prop)}</td></tr>`;}).join("");
  const cur = c.decisions.find(d=>d.state==="current")||c.decisions[0];
  return `<div class="card">
    <h3>Identity &amp; Configuration
      <span class="outcome">&nbsp;${esc(cur?cur.outcome_code:"NO_GOVERNED_DECISION")}</span></h3>
    <div class="intent">Does this request denote a new business identity?</div>
    <table><thead><tr><th>identity property</th><th>value</th>
      <th>provenance</th></tr></thead><tbody>${rows}</tbody></table>
    ${cur?`<dl class="kv" style="margin-top:10px">
      <dt>reason</dt><dd>${esc(cur.reason_code||"—")}</dd>
      <dt>matched rule</dt><dd class="mono">${esc(cur.matched_rule_id||"—")}</dd>
      <dt>governance</dt><dd>${esc(cur.governance_basis)} / ${esc(cur.execution_mode)}</dd>
      <dt>kb</dt><dd class="mono">${esc(cur.kb_version)}</dd>
      <dt>digest</dt><dd class="mono">${esc((cur.input_digest||"").slice(0,32))}…</dd>
    </dl>`:`<p class="empty">No governed decision has been recorded for this
      request.</p>`}
    ${c.missing.length?`<p class="note">Cannot decide: ${c.missing.map(esc).join(", ")}
      ${c.missing.length===1?"has":"have"} not been reported. The request is
      held rather than guessed.</p>`:""}
  </div>`;
}

function render(i){
  CURRENT = CASES[i];
  document.querySelectorAll('#queue tbody tr').forEach(r=>
    r.classList.toggle('sel', +r.dataset.i===i));
  const c = CURRENT;

  /* Overview */
  let ov = "";
  if(c.kind==="sku"){
    ov += `<div class="card"><h3>${esc(c.agent.headline)}</h3>
      <div class="intent">Evidence:
        <b>${c.agent.case.evidence_counts.established}</b> established,
        <b>${c.agent.case.evidence_counts.defaulted}</b> resting on projection
        defaults, <b>${c.agent.case.evidence_counts.unreported}</b> never
        reported.</div>
      ${c.agent.waiting_on?`<dl class="kv">
        <dt>waiting on role</dt><dd>${esc(c.agent.waiting_on.role||"—")}</dd>
        <dt>waiting on person</dt><dd>none — ${esc(c.agent.waiting_on.open_question||"")}</dd>
        <dt>basis</dt><dd>${esc(c.agent.waiting_on.basis)}</dd></dl>`:""}
    </div>`;
    ov += `<div class="card"><h3>Identity &amp; Configuration</h3>
      <p class="empty">No governed property links a SKU to its configuration.
      SKU_MINTED carries a launch id in the raw event, but nothing records it in
      governed state, so this Workbench shows the link as absent rather than
      reaching into raw events to manufacture one.</p></div>`;
    ov += c.agent.case.readiness.map(v=>readinessCard(v,c)).join("");
  } else {
    ov += identityCard(c);
  }
  document.getElementById('p0').innerHTML = ov;

  /* Journey */
  const steps = c.kind==="sku" ? c.agent.journey : [
    {stage:"EVIDENCE", statement:`${Object.keys(c.props).length} identity
      properties folded; ${c.missing.length} not reported`},
    ...c.decisions.map(d=>({stage:"GOVERNED DECISION",
      statement:`${d.decision_type}: ${d.outcome_code} (${d.state})`})),
    {stage:"HANDOFF", statement:"a person decides and acts"}];
  document.getElementById('p1').innerHTML =
    `<ul class="journey">${steps.map(s=>`<li>
      <div class="stage">${esc(s.stage)}</div>
      <div>${esc(s.statement)}</div></li>`).join("")}</ul>
     <p class="note">Decision and handoff, not workflow. Events arrive late and
     out of order; nothing here implies a sequence of process steps.</p>`;

  /* Evidence */
  const props = c.kind==="sku" ? c.agent.case.properties : c.props;
  const names = Object.keys(props).sort();
  document.getElementById('p2').innerHTML = names.length
    ? `<div class="scroll"><table><thead><tr><th>property</th><th>value</th>
        <th>provenance</th><th>state</th><th>basis</th><th>occurred</th>
        <th>arrived</th></tr></thead><tbody>
      ${names.map(n=>{const p=props[n];return `<tr>
        <td>${esc(n)}${p.simulated_actor?' <span class="chip UNREPORTED">simulated actor</span>':""}</td>
        <td>${p.fold_state==="ESTABLISHED"?esc(p.value):"—"}</td>
        <td>${provChip(p)}</td><td>${esc(p.fold_state)}</td>
        <td>${p.basis_count||0}${p.defaulted_count?` (${p.defaulted_count} defaulted)`:""}</td>
        <td>${short(p.effective_at)}</td><td>${short(p.arrival_at)}</td></tr>`}).join("")}
      </tbody></table></div>
      <p class="note">Provenance is per row. A value marked DEFAULTED exists
      because projection logic supplied it, not because any source said so.</p>`
    : `<p class="empty">No folded properties for this subject.</p>`;

  /* Activity & handoffs */
  const drafts = (c.kind==="sku" ? c.agent.communications : []).concat(
    localDrafts[c.id]||[]);
  const arrivals = Object.entries(props)
    .filter(([,p])=>p.arrival_at)
    .sort((a,b)=>String(b[1].arrival_at).localeCompare(String(a[1].arrival_at)))
    .slice(0,12);
  document.getElementById('p3').innerHTML = `
    <div class="actions">
      ${["Send Message","Send Reminder","Request Decision","Escalate","Add Note"]
        .map(a=>`<button data-act="${a}">${a}</button>`).join("")}
    </div>
    <p class="note">Every action drafts. Nothing in this prototype sends mail,
    writes to SAP, FileMaker, Salesforce or ww_pricing, or changes a business
    fact.</p>
    <h2 style="margin-left:0">Communications</h2>
    ${drafts.length?drafts.map(d=>`<div class="draft">
      <b>${esc(d.channel)}</b> <span class="chip UNREPORTED">${esc(d.status)}</span>
      ${d.to_role?` → role <b>${esc(d.to_role)}</b>`:""}
      ${d.to_actor?` → ${esc(d.to_actor)}`:` <span class="note">(no individual named)</span>`}
      <div style="margin-top:6px"><b>${esc(d.subject)}</b></div>
      <pre>${esc(d.body)}</pre></div>`).join(""):`<p class="empty">No drafts.</p>`}
    <h2 style="margin-left:0">Recent evidence arrivals</h2>
    ${arrivals.length?`<div class="scroll"><table><thead><tr><th>arrived</th>
      <th>property</th><th>value</th><th>provenance</th></tr></thead><tbody>
      ${arrivals.map(([n,p])=>`<tr><td>${short(p.arrival_at)}</td>
        <td>${esc(n)}</td><td>${p.fold_state==="ESTABLISHED"?esc(p.value):"—"}</td>
        <td>${provChip(p)}</td></tr>`).join("")}</tbody></table></div>`
      :`<p class="empty">No arrivals recorded.</p>`}`;

  document.querySelector('#p3 .actions').onclick = e=>{
    const b=e.target.closest('button'); if(!b) return;
    const role = c.kind==="sku" && c.agent.waiting_on
      ? c.agent.waiting_on.role : null;
    (localDrafts[c.id] = localDrafts[c.id]||[]).push({
      channel: b.dataset.act==="Add Note" ? "WORKBENCH_NOTE" : "EMAIL_DRAFT",
      status:"DRAFT", to_role:role, to_actor:null,
      subject:`${c.id}: ${b.dataset.act}`,
      body:`${b.dataset.act} drafted from the Workbench against governed state
at horizon ${DATA.horizon}.

This is a simulated action. It has not been sent and no business fact changed.
Addressed to a role, never to an individual: every actor id in this corpus is a
simulation artefact.`});
    render(i);
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
    document.querySelector('.tab[data-t="3"]').classList.add('on');
    document.getElementById('p3').classList.add('on');
  };

  /* Documents */
  document.getElementById('p4').innerHTML = `<p class="empty">No documents are
    attached to governed state in this prototype. Document capture is a
    Claris-side concern and nothing here fabricates one.</p>`;

  /* Related */
  let rel = "";
  if(c.kind==="configuration_request"){
    const key = IDENTITY_PROPS.map(p=>(c.props[p]||{}).value).join("|");
    const siblings = CASES.filter(o=>o.kind==="configuration_request"
      && o.id!==c.id
      && IDENTITY_PROPS.map(p=>(o.props[p]||{}).value).join("|")===key);
    rel = siblings.length
      ? `<p>Requests resolving to the same business identity:</p>
         <div class="scroll"><table><thead><tr><th>request</th><th>decision</th>
         </tr></thead><tbody>${siblings.map(s=>`<tr><td>${esc(s.id)}</td>
         <td>${esc(s.state)}</td></tr>`).join("")}</tbody></table></div>
         <p class="note">Same canonical identity, so the later ones are
         duplicates rather than new configurations. This is the proliferation
         the platform prevents.</p>`
      : `<p class="empty">No other request resolves to this identity.</p>`;
  } else {
    const cfgs = DATA.configurations||[];
    rel = cfgs.length ? `<p>Canonical configurations in the platform:</p>
      <div class="scroll"><table><thead><tr><th>configuration</th><th>product</th>
      <th>versions</th><th>canonical identity</th></tr></thead><tbody>
      ${cfgs.map(x=>`<tr><td>${esc(x.configuration_id)}</td>
        <td>${esc(x.product_id)}</td><td>${x.versions}</td>
        <td class="mono">${esc(x.canonical_identity)}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="note">No governed property links this SKU to one of them.</p>`
      : `<p class="empty">No configurations.</p>`;
  }
  document.getElementById('p5').innerHTML = rel;
}

tbody.onclick = e => { const r=e.target.closest('tr'); if(r) render(+r.dataset.i); };
render(0);
</script>
</body>
</html>
"""


def main() -> int:
    src = os.path.join(OUT, "workbench_data.json")
    if not os.path.exists(src):
        print(f"missing {src}\nrun: python workbench\\collect.py")
        return 4
    with open(src, encoding="utf-8") as handle:
        data = handle.read()
    # </script> inside the payload would end the block early.
    payload = data.replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", payload)
    path = os.path.join(OUT, "workbench.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    print(f"wrote {path}  ({len(html):,} bytes)")
    print("open it directly in a browser -- no server needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
