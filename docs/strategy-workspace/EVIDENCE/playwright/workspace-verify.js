const { chromium } = require('/tmp/opencode/pwcheck/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('console', m => { if (m.type()==='error') errors.push('console: '+m.text()); });
  page.on('pageerror', e => errors.push('pageerror: '+e.message));
  await page.goto('http://127.0.0.1:16900/', {waitUntil:'networkidle'});
  await page.getByRole('button', {name:'Strategy Workspace'}).click();
  await page.waitForTimeout(600);
  console.log('list_heading=' + await page.locator('h1').innerText());
  console.log('cards=' + await page.locator('.workspace-card').count());
  await page.getByPlaceholder('Title, ID, tag or description').fill('Liquidity');
  await page.waitForTimeout(500);
  console.log('search_results=' + await page.locator('.workspace-card').count());
  await page.getByPlaceholder('Title, ID, tag or description').fill('');
  await page.waitForTimeout(500);
  await page.locator('.workspace-card').filter({hasText:'Liquidity Sweep'}).click();
  await page.waitForTimeout(800);
  console.log('detail_heading=' + await page.locator('h1').innerText());
  for (const label of ['Overview','Rules','Notes','Variations','Experiments','Comparison']) {
    await page.getByRole('tab', {name:new RegExp('^'+label)}).click();
    await page.waitForTimeout(150);
    console.log('tab_'+label+'_visible=' + (await page.getByRole('tab', {name:new RegExp('^'+label)}).getAttribute('aria-selected')));
  }
  // return to experiments to confirm actual linked run
  await page.getByRole('tab', {name:/Experiments/}).click();
  await page.waitForTimeout(500);
  console.log('experiment_rows=' + await page.locator('table tbody tr').count());
  console.log('has_run_link=' + (await page.locator('body').innerText()).includes('20261103T144626Z_57dd08ff'));
  console.log('console_errors=' + errors.length);
  await page.screenshot({path:'/tmp/opencode/qa-workspace/final-workspace.png',fullPage:true});
  await browser.close();
})();
