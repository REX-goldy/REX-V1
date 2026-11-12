const { chromium } = require('/tmp/opencode/pwcheck/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];
  page.on('console', m => { if (m.type()==='error') errors.push('console: '+m.text()); });
  page.on('pageerror', e => errors.push('pageerror: '+e.message));
  await page.goto('http://127.0.0.1:16900/', {waitUntil:'networkidle'});
  console.log('title', await page.title());
  console.log('nav', await page.getByRole('button', {name:'Strategy Workspace'}).count());
  await page.getByRole('button', {name:'Strategy Workspace'}).click();
  await page.waitForTimeout(500);
  console.log('h1', await page.locator('h1').innerText());
  console.log('cards', await page.locator('.workspace-card').count());
  console.log('errors', errors);
  await page.screenshot({path:'/tmp/opencode/qa-workspace/workspace-list.png', fullPage:true});
  await browser.close();
})();
