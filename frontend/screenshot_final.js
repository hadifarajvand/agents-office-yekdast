import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  console.log('Taking screenshot of fixed UI...\n');
  
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  
  // Get task info
  const taskInfo = await page.evaluate(() => {
    const allTaskText = document.body.textContent;
    return {
      hasEmailsTask: allTaskText.includes('emails department'),
      hasSalesTask: allTaskText.includes('sales department'),
      hasMarketingTask: allTaskText.includes('marketing department'),
      taskCount: allTaskText.match(/ALL (\d+)/)?.[1] || '?'
    };
  });
  
  console.log('UI Content Check:');
  console.log('  Emails task:', taskInfo.hasEmailsTask ? '✅' : '❌');
  console.log('  Sales task:', taskInfo.hasSalesTask ? '✅' : '❌');
  console.log('  Marketing task:', taskInfo.hasMarketingTask ? '✅' : '❌');
  console.log('  Task count: ALL', taskInfo.taskCount);
  
  await page.screenshot({ path: 'C:/Users/EndWay/AppData/Local/Temp/claude/ui-fixed.png' });
  console.log('\n✅ Screenshot saved: ui-fixed.png');
  
  await browser.close();
})();
