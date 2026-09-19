import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Listen to all API calls
  await page.on('response', response => {
    if (response.url().includes('/api/')) {
      console.log(`📡 API: ${response.url().split('/api/')[1]}`);
      console.log(`   Status: ${response.status()}`);
      if (response.status() === 200) {
        response.json().then(data => {
          console.log(`   Response: ${JSON.stringify(data).substring(0, 100)}`);
        }).catch(() => {});
      }
    }
  });
  
  console.log('🔗 CHECKING BACKEND CONNECTION\n');
  
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
  
  console.log('\n✅ Page loaded');
  console.log('Waiting for polling...\n');
  
  // Wait for polling calls
  await page.waitForTimeout(10000);
  
  console.log('\n📊 Checking what tasks the frontend has...');
  const frontendState = await page.evaluate(() => {
    // Try to access window state or task data
    return {
      window_keys: Object.keys(window).filter(k => k.toLowerCase().includes('task') || k.toLowerCase().includes('agent')).slice(0, 10),
      all_text_with_done: Array.from(document.querySelectorAll('*'))
        .filter(el => el.textContent?.includes('DONE'))
        .map(el => el.textContent?.trim())
        .slice(0, 5)
    };
  });
  
  console.log('Frontend state:', frontendState);
  
  await browser.close();
})();
