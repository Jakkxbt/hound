import asyncio
import json
from flask import Flask, request, jsonify, Response, render_template_string
from .engine import hunt
from .modules import ALL_MODULES

app = Flask(__name__)


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/hunt", methods=["POST"])
def api_hunt():
    data = request.json or {}
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    def generate():
        async def run():
            import httpx
            sem = asyncio.Semaphore(10)
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
            async with httpx.AsyncClient(timeout=12, follow_redirects=True, limits=limits) as client:
                async def one(mod):
                    async with sem:
                        r = await mod(client, email)
                        return r
                tasks = [one(m) for m in ALL_MODULES]
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    yield result

        async def collect():
            results = []
            async for r in run():
                results.append(r)
                yield f"data: {json.dumps(r)}\n\n"
            yield "data: [DONE]\n\n"

        loop = asyncio.new_event_loop()
        gen = collect()
        try:
            while True:
                chunk = loop.run_until_complete(gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOUND — Email OSINT</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0c10;--surface:#111520;--card:#141824;--border:#1e2535;
      --text:#d8dce8;--muted:#5a6070;--dim:#2a3040;
      --green:#00e676;--red:#ff5252;--amber:#ffc107;--blue:#40c4ff}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;
     min-height:100vh;display:flex;flex-direction:column}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);
        padding:.75rem 1.5rem;display:flex;align-items:center;gap:.8rem}
.brand{font-family:monospace;font-size:1.1rem;font-weight:700;color:var(--green);
       letter-spacing:.2em}
.sub{font-size:.7rem;color:var(--muted);letter-spacing:.1em}
.main{flex:1;max-width:900px;margin:0 auto;padding:2rem 1.2rem;width:100%;
      display:flex;flex-direction:column;gap:1.5rem}
.search-box{background:var(--surface);border:1px solid var(--border);border-radius:6px;
            padding:1.2rem 1.4rem;display:flex;gap:.7rem;align-items:center}
.email-input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);
             font-size:.95rem;padding:.6rem .9rem;border-radius:4px;outline:none;
             font-family:'Courier New',monospace}
.email-input:focus{border-color:var(--green)}
.email-input::placeholder{color:var(--dim)}
.btn-hunt{background:var(--green);color:#000;border:none;padding:.6rem 1.4rem;
          border-radius:4px;font-size:.85rem;font-weight:700;cursor:pointer;
          letter-spacing:.08em;white-space:nowrap}
.btn-hunt:hover{background:#33ff88}
.btn-hunt:disabled{opacity:.4;cursor:not-allowed}
.stats-row{display:flex;gap:.6rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:4px;
      padding:.6rem 1rem;font-size:.78rem}
.stat-val{font-size:1.3rem;font-weight:700;display:block}
.stat-val.green{color:var(--green)}
.stat-val.muted{color:var(--muted)}
.stat-val.amber{color:var(--amber)}
.results{display:flex;flex-direction:column;gap:.3rem}
.result-row{background:var(--card);border:1px solid var(--border);border-radius:4px;
            padding:.5rem .9rem;display:flex;align-items:center;gap:.8rem;
            transition:border-color .15s}
.result-row.found{border-left:3px solid var(--green)}
.result-row.not-found{opacity:.5}
.result-row.unknown{border-left:3px solid var(--amber)}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.found{background:var(--green);box-shadow:0 0 6px var(--green)}
.dot.not-found{background:var(--dim)}
.dot.unknown{background:var(--amber)}
.site-name{font-size:.82rem;font-weight:600;width:160px;flex-shrink:0}
.site-status{font-size:.75rem;width:90px;flex-shrink:0}
.site-status.found{color:var(--green)}
.site-status.not-found{color:var(--muted)}
.site-status.unknown{color:var(--amber)}
.site-url{font-size:.7rem;color:var(--muted);font-family:monospace;flex:1;
          overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.site-url a{color:var(--blue);text-decoration:none}
.site-url a:hover{text-decoration:underline}
.progress-bar{background:var(--border);border-radius:2px;height:3px;overflow:hidden;margin-top:.5rem}
.progress-fill{background:var(--green);height:100%;transition:width .3s;width:0%}
.empty{color:var(--muted);font-size:.8rem;padding:1.5rem;text-align:center}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
</style></head><body>
<div class="topbar">
  <div class="brand">HOUND</div>
  <div class="sub">EMAIL OSINT</div>
</div>
<div class="main">
  <div class="search-box">
    <input class="email-input" id="email-input" type="email"
      placeholder="target@example.com"
      onkeydown="if(event.key==='Enter')startHunt()">
    <button class="btn-hunt" id="hunt-btn" onclick="startHunt()">▶ HUNT</button>
  </div>
  <div class="progress-bar" id="progress-bar" style="display:none">
    <div class="progress-fill" id="progress-fill"></div>
  </div>
  <div class="stats-row" id="stats-row" style="display:none">
    <div class="stat"><span class="stat-val green" id="s-found">0</span>Found</div>
    <div class="stat"><span class="stat-val muted" id="s-nf">0</span>Not Found</div>
    <div class="stat"><span class="stat-val amber" id="s-unk">0</span>Unknown</div>
    <div class="stat"><span class="stat-val muted" id="s-total">0</span>Checked</div>
  </div>
  <div class="results" id="results">
    <div class="empty" id="empty-msg">Enter an email address above and press HUNT.</div>
  </div>
</div>

<script>
let total = 27, checked = 0, found = 0, nf = 0, unk = 0;

function startHunt() {
  const email = document.getElementById('email-input').value.trim();
  if (!email || !email.includes('@')) { alert('Enter a valid email'); return; }

  checked = found = nf = unk = 0;
  document.getElementById('results').innerHTML = '';
  document.getElementById('empty-msg') && document.getElementById('results').appendChild(
    Object.assign(document.createElement('div'), {className:'empty', textContent:'Scanning...'}));
  document.getElementById('stats-row').style.display = 'flex';
  document.getElementById('progress-bar').style.display = 'block';
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('hunt-btn').disabled = true;
  document.getElementById('hunt-btn').textContent = '... hunting';
  updateStats();

  const es = new EventSource('/api/hunt?' + new URLSearchParams({_: Date.now()}));
  fetch('/api/hunt', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email})
  }).then(r => {
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    const list = document.getElementById('results');
    list.innerHTML = '';

    function read() {
      reader.read().then(({done, value}) => {
        if (done) {
          document.getElementById('hunt-btn').disabled = false;
          document.getElementById('hunt-btn').textContent = '▶ HUNT';
          document.getElementById('progress-fill').style.width = '100%';
          return;
        }
        buf += dec.decode(value, {stream: true});
        const lines = buf.split('\\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') {
            document.getElementById('hunt-btn').disabled = false;
            document.getElementById('hunt-btn').textContent = '▶ HUNT';
            return;
          }
          try {
            const r = JSON.parse(payload);
            addResult(r, list);
          } catch {}
        }
        read();
      });
    }
    read();
  }).catch(e => {
    document.getElementById('hunt-btn').disabled = false;
    document.getElementById('hunt-btn').textContent = '▶ HUNT';
    alert('Error: ' + e.message);
  });
}

function addResult(r, list) {
  checked++;
  if (r.found === true) found++;
  else if (r.found === false) nf++;
  else unk++;

  updateStats();
  document.getElementById('progress-fill').style.width = Math.round(checked / total * 100) + '%';

  const cls = r.found === true ? 'found' : r.found === false ? 'not-found' : 'unknown';
  const statusText = r.found === true ? '● FOUND' : r.found === false ? '○ not found' : '? ' + (r.error||'unknown').slice(0,20);
  const row = document.createElement('div');
  row.className = 'result-row ' + cls;
  row.innerHTML = \`
    <div class="dot \${cls}"></div>
    <div class="site-name">\${esc(r.name)}</div>
    <div class="site-status \${cls}">\${esc(statusText)}</div>
    <div class="site-url"><a href="\${esc(r.url)}" target="_blank">\${esc(r.url)}</a></div>
  \`;
  if (r.found === true) list.prepend(row);
  else list.appendChild(row);
}

function updateStats() {
  document.getElementById('s-found').textContent = found;
  document.getElementById('s-nf').textContent = nf;
  document.getElementById('s-unk').textContent = unk;
  document.getElementById('s-total').textContent = checked;
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}
</script>
</body></html>"""


def run(host="0.0.0.0", port=5100, debug=False):
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run()
