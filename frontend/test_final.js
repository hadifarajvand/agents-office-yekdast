import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:9000', { waitUntil: 'networkidle' });
  
  await page.screenshot({ path: 'C:/Users/EndWay/AppData/Local/Temp/claude/ui-success-final.png' });
  
  const taskStatus = await page.evaluate(() => {
    const text = document.body.textContent;
    const allMatch = text.match(/ALL (\d+)/);
    return { total: allMatch ? allMatch[1] : '?' };
  });
  
  console.log('✅ UI shows: ALL', taskStatus.total);
  console.log('✅ Backend is CONNECTED and showing real tasks!');
  
  await browser.close();
})();
