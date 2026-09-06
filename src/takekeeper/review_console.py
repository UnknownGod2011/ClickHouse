from __future__ import annotations

from .review_api import ReviewHttpApp


_CONSOLE_HTML = b'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TakeKeeper Review Console</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color-scheme:dark;background:#0d1117;color:#e6edf3}
body{margin:0}.shell{max-width:1100px;margin:auto;padding:28px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;margin:14px 0}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}label{display:grid;gap:6px;font-size:12px;color:#9da7b3}input,select,textarea,button{font:inherit;border-radius:6px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;padding:9px}textarea{width:100%;min-height:70px;box-sizing:border-box}button{cursor:pointer;background:#238636;border-color:#2ea043;font-weight:650}button.secondary{background:#21262d;border-color:#30363d}.muted{color:#9da7b3}.status{font-weight:700}.ok{color:#3fb950}.warn{color:#d29922}.bad{color:#f85149}.evidence{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.metric{background:#0d1117;padding:10px;border-radius:6px;border:1px solid #21262d}.metric b{display:block;margin-top:4px}.history{display:grid;gap:8px}.history article{border-left:3px solid #30363d;padding:8px 12px;background:#0d1117}.error{white-space:pre-wrap;color:#f85149}.hidden{display:none}code{font-family:ui-monospace,SFMono-Regular,monospace}
</style>
</head>
<body><main class="shell">
<h1>TakeKeeper Review Console</h1>
<p class="muted">Inspect one scoped continuity finding and append a human disposition. Credentials are kept only in this page session and are never stored by the console.</p>
<section class="card">
<div class="grid">
<label>Bearer token<input id="token" type="password" autocomplete="off" spellcheck="false"></label>
<label>Production<input id="production_id" value="glass-house"></label>
<label>Scene<input id="scene_id" value="S28"></label>
<label>Take<input id="take_id" value="S28-T47"></label>
<label>Entity<input id="entity_id" value="maya"></label>
<label>Property<input id="property_key" value="prop.mug_hand"></label>
</div>
<div class="row" style="margin-top:14px"><button id="load">Load finding</button><span id="request-status" class="muted"></span></div>
<p id="error" class="error hidden"></p>
</section>
<section id="finding-card" class="card hidden">
<div class="row"><h2 style="margin-right:auto">Finding</h2><span id="finding-status" class="status"></span></div>
<div class="evidence">
<div class="metric">Baseline<b id="baseline"></b></div><div class="metric">Observed<b id="observed"></b></div><div class="metric">Confidence<b id="confidence"></b></div><div class="metric">Evidence window<b id="window"></b></div><div class="metric">Baseline source take<b id="source-take"></b></div><div class="metric">Finding ID<b><code id="finding-id"></code></b></div>
</div>
</section>
<section id="decision-card" class="card hidden">
<h2>Record review</h2><div class="grid"><label>Decision<select id="decision"><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option><option value="needs_followup">Needs follow-up</option></select></label></div>
<label style="margin-top:12px">Note<textarea id="note" maxlength="2000" placeholder="Optional review evidence or rationale"></textarea></label>
<div class="row" style="margin-top:12px"><button id="submit">Append decision</button><span class="muted">Append-only: prior decisions remain visible.</span></div>
</section>
<section id="history-card" class="card hidden"><h2>Review history</h2><div id="history" class="history"></div></section>
</main>
<script>
const ids=['production_id','scene_id','take_id','entity_id','property_key'];
const el=id=>document.getElementById(id);
const scope=()=>Object.fromEntries(ids.map(id=>[id,el(id).value.trim()]));
function auth(){const token=el('token').value;if(!token)throw new Error('Bearer token is required.');return {'Authorization':'Bearer '+token,'Content-Type':'application/json'};}
async function request(path,payload){el('request-status').textContent='Working…';el('error').classList.add('hidden');try{const res=await fetch(path,{method:'POST',headers:auth(),body:JSON.stringify(payload),cache:'no-store',credentials:'same-origin'});const data=await res.json();if(!res.ok)throw new Error(data.error||('Request failed: '+res.status));return data;}finally{el('request-status').textContent='';}}
function render(data){const f=data.finding;el('finding-card').classList.remove('hidden');el('decision-card').classList.remove('hidden');el('history-card').classList.remove('hidden');el('finding-status').textContent=f.status;el('finding-status').className='status '+(f.status==='mismatch'?'bad':f.status==='uncertain'?'warn':'ok');el('baseline').textContent=f.baseline_value??'—';el('observed').textContent=f.observed_value??'—';el('confidence').textContent=typeof f.confidence==='number'?(f.confidence*100).toFixed(1)+'%':'—';el('window').textContent=(f.evidence_start_ms??'—')+'–'+(f.evidence_end_ms??'—')+' ms';el('source-take').textContent=f.baseline_source_take_id??'—';el('finding-id').textContent=f.finding_id??'—';const h=el('history');h.replaceChildren();if(!data.history.length){const p=document.createElement('p');p.className='muted';p.textContent='No decisions recorded yet.';h.appendChild(p);return;}for(const row of data.history){const a=document.createElement('article');const title=document.createElement('strong');title.textContent=row.decision+' — '+row.actor_id;const meta=document.createElement('div');meta.className='muted';meta.textContent=row.created_at||'';a.append(title,meta);if(row.note){const note=document.createElement('p');note.textContent=row.note;a.appendChild(note);}h.appendChild(a);}}
async function load(){try{render(await request('/v1/review/context',scope()));}catch(e){el('error').textContent=e.message;el('error').classList.remove('hidden');}}
el('load').addEventListener('click',load);
el('submit').addEventListener('click',async()=>{try{await request('/v1/review/decision',{...scope(),decision:el('decision').value,note:el('note').value});el('note').value='';await load();}catch(e){el('error').textContent=e.message;el('error').classList.remove('hidden');}});
</script></body></html>'''


class ReviewConsoleApp:
    """Same-origin operator UI wrapper around the narrow review API.

    GET /review serves a dependency-free console. Every other request is delegated
    unchanged to ReviewHttpApp, preserving its authentication, scope validation,
    body limits, and append-only decision semantics.
    """

    def __init__(self, api: ReviewHttpApp) -> None:
        self._api = api

    def __call__(self, environ, start_response):
        method = str(environ.get("REQUEST_METHOD", "")).upper()
        path = str(environ.get("PATH_INFO", ""))
        if path == "/review":
            if method != "GET":
                body = b"method not allowed"
                start_response("405 Method Not Allowed", self._headers("text/plain; charset=utf-8", len(body)))
                return [body]
            start_response("200 OK", self._headers("text/html; charset=utf-8", len(_CONSOLE_HTML)))
            return [_CONSOLE_HTML]
        return self._api(environ, start_response)

    @staticmethod
    def _headers(content_type: str, length: int):
        return [
            ("Content-Type", content_type),
            ("Content-Length", str(length)),
            ("Cache-Control", "no-store"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            (
                "Content-Security-Policy",
                "default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ),
        ]
