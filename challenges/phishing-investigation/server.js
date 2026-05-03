const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;

const emails = JSON.parse(fs.readFileSync(path.join(__dirname, 'emails.json'), 'utf8'));

const PAGE_STYLE = `
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
        background: #0a0e17;
        color: #c9d1d9;
        min-height: 100vh;
    }
    .header {
        background: #161b22;
        border-bottom: 1px solid #30363d;
        padding: 20px 40px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header h1 {
        color: #58a6ff;
        font-size: 1.4em;
    }
    .header .badge {
        background: #da3633;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85em;
    }
    .container {
        max-width: 900px;
        margin: 30px auto;
        padding: 0 20px;
    }
    .instructions {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        color: #8b949e;
        line-height: 1.6;
    }
    .instructions strong { color: #f0883e; }
    .email-list { list-style: none; }
    .email-item {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: border-color 0.2s;
        display: flex;
        justify-content: space-between;
        align-items: center;
        text-decoration: none;
        color: inherit;
    }
    .email-item:hover { border-color: #58a6ff; }
    .email-from { color: #e6edf3; font-weight: 600; margin-bottom: 4px; }
    .email-subject { color: #c9d1d9; }
    .email-date { color: #8b949e; font-size: 0.85em; white-space: nowrap; }
    .email-meta { flex-shrink: 0; margin-left: 20px; }

    .email-detail {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 30px;
    }
    .email-detail h2 { color: #e6edf3; margin-bottom: 20px; }
    .email-field { margin-bottom: 8px; }
    .email-field .label { color: #8b949e; display: inline-block; width: 60px; }
    .email-field .value { color: #c9d1d9; }
    .email-body {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 20px;
        margin-top: 20px;
        white-space: pre-wrap;
        line-height: 1.6;
        font-family: monospace;
    }
    .headers-toggle {
        background: #21262d;
        color: #58a6ff;
        border: 1px solid #30363d;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        margin-top: 20px;
        font-size: 0.9em;
    }
    .headers-toggle:hover { background: #30363d; }
    .headers-section {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 20px;
        margin-top: 10px;
        font-family: monospace;
        font-size: 0.85em;
        display: none;
    }
    .headers-section.visible { display: block; }
    .header-line { margin-bottom: 6px; }
    .header-line .hname { color: #f0883e; }
    .header-line .hval { color: #7ee787; }
    .back-link {
        display: inline-block;
        color: #58a6ff;
        text-decoration: none;
        margin-bottom: 20px;
    }
    .back-link:hover { text-decoration: underline; }
    .spf-fail { color: #da3633 !important; font-weight: bold; }
`;

app.get('/', (req, res) => {
    let emailListHtml = '';
    for (const email of emails) {
        const d = new Date(email.date);
        const dateStr = d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        emailListHtml += `
            <a href="/email/${email.id}" class="email-item">
                <div>
                    <div class="email-from">${escapeHtml(email.from)}</div>
                    <div class="email-subject">${escapeHtml(email.subject)}</div>
                </div>
                <div class="email-meta">
                    <span class="email-date">${dateStr}</span>
                </div>
            </a>`;
    }

    res.send(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Inbox - Phishing Investigation</title>
    <style>${PAGE_STYLE}</style>
</head>
<body>
    <div class="header">
        <h1>Inbox - Phishing Investigation</h1>
        <span class="badge">${emails.length} messages</span>
    </div>
    <div class="container">
        <div class="instructions">
            <strong>Mission:</strong> One of the emails in this inbox is a phishing attempt.
            Analyze the sender addresses, email headers, and content carefully.
            Find the phishing email and extract the hidden flag from it.
        </div>
        <div class="email-list">
            ${emailListHtml}
        </div>
    </div>
</body>
</html>`);
});

app.get('/email/:id', (req, res) => {
    const id = parseInt(req.params.id);
    const email = emails.find(e => e.id === id);

    if (!email) {
        return res.status(404).send('Email not found');
    }

    let headersHtml = '';
    for (const [key, value] of Object.entries(email.headers)) {
        const isFail = key === 'SPF' && value.includes('Fail');
        headersHtml += `<div class="header-line">
            <span class="hname">${escapeHtml(key)}:</span>
            <span class="hval${isFail ? ' spf-fail' : ''}">${escapeHtml(value)}</span>
        </div>`;
    }

    const d = new Date(email.date);
    const dateStr = d.toLocaleString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
    });

    res.send(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${escapeHtml(email.subject)} - Phishing Investigation</title>
    <style>${PAGE_STYLE}</style>
</head>
<body>
    <div class="header">
        <h1>Email Detail</h1>
    </div>
    <div class="container">
        <a href="/" class="back-link">&larr; Back to Inbox</a>
        <div class="email-detail">
            <h2>${escapeHtml(email.subject)}</h2>
            <div class="email-field">
                <span class="label">From:</span>
                <span class="value">${escapeHtml(email.from)}</span>
            </div>
            <div class="email-field">
                <span class="label">To:</span>
                <span class="value">${escapeHtml(email.to)}</span>
            </div>
            <div class="email-field">
                <span class="label">Date:</span>
                <span class="value">${dateStr}</span>
            </div>
            <div class="email-body">${escapeHtml(email.body)}</div>

            <button class="headers-toggle" onclick="document.getElementById('headers').classList.toggle('visible')">
                Toggle Email Headers
            </button>
            <div id="headers" class="headers-section">
                ${headersHtml}
            </div>
        </div>
    </div>
</body>
</html>`);
});

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Phishing Investigation running on port ${PORT}`);
});
