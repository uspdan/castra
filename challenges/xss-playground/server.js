const express = require('express');
const bot = require('./bot');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const caughtData = [];

app.get('/', (req, res) => {
  const q = req.query.q || '';
  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>XSS Playground - Search</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 20px; }
    h1 { color: #00ff88; margin-bottom: 30px; font-size: 2em; }
    .search-box { background: #1a1a2e; padding: 30px; border-radius: 10px; border: 1px solid #333; width: 100%; max-width: 600px; margin-bottom: 20px; }
    form { display: flex; gap: 10px; }
    input[type="text"] { flex: 1; padding: 12px; background: #0f0f1a; border: 1px solid #444; border-radius: 5px; color: #fff; font-size: 16px; }
    button { padding: 12px 24px; background: #00ff88; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; }
    button:hover { background: #00cc6a; }
    .results { background: #1a1a2e; padding: 20px; border-radius: 10px; border: 1px solid #333; width: 100%; max-width: 600px; margin-bottom: 20px; }
    .results h2 { color: #00ff88; margin-bottom: 10px; }
    .report-box { background: #1a1a2e; padding: 30px; border-radius: 10px; border: 1px solid #333; width: 100%; max-width: 600px; }
    .report-box h2 { color: #ff6600; margin-bottom: 15px; }
    .report-box p { margin-bottom: 10px; color: #aaa; }
    #report-url { flex: 1; padding: 12px; background: #0f0f1a; border: 1px solid #444; border-radius: 5px; color: #fff; font-size: 16px; }
    .report-btn { background: #ff6600 !important; }
    .report-btn:hover { background: #cc5200 !important; }
    #report-status { margin-top: 10px; color: #aaa; }
    .hint { background: #2a1a00; border: 1px solid #ff6600; padding: 15px; border-radius: 5px; margin-top: 20px; width: 100%; max-width: 600px; }
    .hint p { color: #ffaa44; }
  </style>
</head>
<body>
  <h1>XSS Playground</h1>

  <div class="search-box">
    <form method="GET" action="/">
      <input type="text" name="q" placeholder="Search..." value="">
      <button type="submit">Search</button>
    </form>
  </div>

  ${q ? `<div class="results">
    <h2>Search Results for: ${q}</h2>
    <p>No results found for your query.</p>
  </div>` : ''}

  <div class="report-box">
    <h2>Report a URL to Admin</h2>
    <p>Found something interesting? Submit a URL for the admin bot to review.</p>
    <form id="report-form" style="display:flex;gap:10px;">
      <input type="text" id="report-url" placeholder="https://...">
      <button type="submit" class="report-btn">Report</button>
    </form>
    <div id="report-status"></div>
  </div>

  <div class="hint">
    <p><strong>Hint:</strong> The admin bot has a cookie with a secret flag. Can you steal it?</p>
  </div>

  <script>
    document.getElementById('report-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const url = document.getElementById('report-url').value;
      const status = document.getElementById('report-status');
      status.textContent = 'Submitting to admin bot...';
      try {
        const resp = await fetch('/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
        const data = await resp.json();
        status.textContent = data.message;
      } catch (err) {
        status.textContent = 'Error: ' + err.message;
      }
    });
  </script>
</body>
</html>`);
});

app.post('/report', async (req, res) => {
  const { url } = req.body;
  if (!url) {
    return res.json({ message: 'Please provide a URL' });
  }
  try {
    await bot.visit(url);
    res.json({ message: 'Admin bot visited the URL successfully.' });
  } catch (err) {
    console.error('Bot error:', err.message);
    res.json({ message: 'Admin bot encountered an error visiting the URL.' });
  }
});

app.get('/catcher', (req, res) => {
  const data = req.query.data || '';
  const timestamp = new Date().toISOString();
  caughtData.push({ data, timestamp });
  console.log(`[CATCHER] ${timestamp}: ${data}`);
  res.send('OK');
});

app.get('/catcher/log', (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Catcher Log</title>
  <style>
    body { font-family: monospace; background: #0a0a0a; color: #00ff88; padding: 20px; }
    h1 { margin-bottom: 20px; }
    .entry { background: #1a1a2e; padding: 10px; margin-bottom: 5px; border-radius: 5px; border: 1px solid #333; }
    .timestamp { color: #888; }
    .data { color: #ff6600; word-break: break-all; }
  </style>
</head>
<body>
  <h1>Catcher Log (${caughtData.length} entries)</h1>
  ${caughtData.length === 0 ? '<p>No data caught yet.</p>' : caughtData.map(entry => `
    <div class="entry">
      <span class="timestamp">${entry.timestamp}</span><br>
      <span class="data">${entry.data}</span>
    </div>
  `).join('')}
  <script>setTimeout(() => location.reload(), 5000);</script>
</body>
</html>`);
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`XSS Playground running on port ${PORT}`);
});
