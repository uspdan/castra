// PrefsHub — a "save my UI preferences" endpoint that does an
// unsafe recursive merge of the request body into the per-session
// preferences object. Walking through the merge with a body that
// contains "__proto__" keys mutates Object.prototype globally —
// every plain object on the server now has the polluted property.
//
// The /admin route gates on `req.session.isAdmin`. New sessions
// don't set isAdmin at all. After pollution, the property
// resolves up the prototype chain to the polluted value.

const express = require('express');

const app = express();
app.use(express.json({ limit: '64kb' }));

const FLAG = 'CTF{REDACTED}';
const SESSIONS = Object.create(null);  // safe — but the prefs INSIDE are not

function newSession() {
  const id = Math.random().toString(36).slice(2, 12);
  SESSIONS[id] = { id, prefs: {} };  // bare {} — inherits Object.prototype
  return SESSIONS[id];
}

// Vulnerable recursive merge — happily walks "__proto__" / "constructor"
// keys without filtering, mutating Object.prototype when given.
function deepMerge(target, src) {
  for (const key of Object.keys(src)) {
    const v = src[key];
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      if (typeof target[key] !== 'object' || target[key] === null) {
        target[key] = {};
      }
      deepMerge(target[key], v);
    } else {
      target[key] = v;
    }
  }
  return target;
}

function getSession(req) {
  const sid = req.header('x-session') || req.query.sid;
  if (sid && SESSIONS[sid]) return SESSIONS[sid];
  const fresh = newSession();
  return fresh;
}

app.get('/', (req, res) => {
  const s = getSession(req);
  res.type('html').send(`<!doctype html>
<html><head><title>PrefsHub</title><style>
body{font-family:system-ui;background:#0c0c18;color:#eee;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>PrefsHub</h1>
<p class="muted">A tiny UI-preferences endpoint. POST your prefs, GET them back.</p>

<div class="card">
  <div class="muted">your session id</div>
  <div><code>${s.id}</code></div>
  <p class="muted" style="margin-top:8px;">Pass this back as the <code>X-Session</code> header on every request.</p>
</div>

<div class="card">
  <strong>Endpoints</strong>
  <pre>
POST /prefs       { "theme": "dark", "lang": "en" }   # deep-merge into your saved prefs
GET  /prefs                                            # current saved prefs
GET  /admin                                            # admin-only; gated on session.isAdmin
  </pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The merge is unfortunately deep and trusting.</p>
</div>
</body></html>`);
});

app.post('/prefs', (req, res) => {
  const s = getSession(req);
  const body = req.body || {};
  // VULNERABLE: no filtering of __proto__ / constructor keys.
  deepMerge(s.prefs, body);
  res.json({ ok: true, prefs: s.prefs, sid: s.id });
});

app.get('/prefs', (req, res) => {
  const s = getSession(req);
  res.json({ prefs: s.prefs, sid: s.id });
});

app.get('/admin', (req, res) => {
  const s = getSession(req);
  // Gated on a per-session flag that NEW sessions never set. After
  // Object.prototype pollution, the property resolves through the
  // prototype chain.
  if (s.isAdmin) {
    return res.json({ flag: FLAG });
  }
  return res.status(403).json({ error: 'admin only', hint: 'session.isAdmin is unset' });
});

app.listen(3000, '0.0.0.0', () => {
  console.log('PrefsHub listening on :3000');
});
