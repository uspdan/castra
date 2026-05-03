const puppeteer = require('puppeteer-core');

module.exports = {
  async visit(url) {
    const browser = await puppeteer.launch({
      executablePath: '/usr/bin/chromium-browser',
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
      ]
    });

    try {
      const page = await browser.newPage();

      await page.setCookie({
        name: 'flag',
        value: 'CTF{REDACTED}',
        domain: 'localhost',
        path: '/',
        httpOnly: false,
        secure: false
      });

      await page.goto(url, {
        waitUntil: 'networkidle2',
        timeout: 10000
      });

      await new Promise(resolve => setTimeout(resolve, 3000));

      await page.close();
    } finally {
      await browser.close();
    }
  }
};
