import { chromium } from 'playwright';

async function investigateAutoTasks() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  // Enable console logging
  page.on('console', msg => console.log('[PAGE]', msg.text()));
  page.on('response', response => {
    if (response.url().includes('/api/tasks')) {
      console.log(`[API] ${response.request().method()} ${response.url()} → ${response.status()}`);
    }
  });

  console.log('');
  console.log('Opening Agent Office UI...');
  console.log('===================================');
  console.log('');

  // Get initial task count
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });

  // Wait a moment for initial load
  await page.waitForTimeout(2000);

  // Get task count
  let initialCount = await page.evaluate(() => {
    const taskCards = document.querySelectorAll('[data-task-id]');
    return taskCards.length;
  });

  console.log(`Initial task count: ${initialCount}`);
  console.log('');
  console.log('Monitoring for auto-generated tasks over 30 seconds...');
  console.log('===================================');
  console.log('');

  // Check for new tasks every 2 seconds
  let previousCount = initialCount;
  const startTime = Date.now();
  const duration = 30000; // 30 seconds
  let newTaskDetected = false;

  while (Date.now() - startTime < duration) {
    await page.waitForTimeout(2000);

    const currentCount = await page.evaluate(() => {
      const taskCards = document.querySelectorAll('[data-task-id]');
      return taskCards.length;
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    if (currentCount !== previousCount) {
      console.log(`[${elapsed}s] Task count changed: ${previousCount} → ${currentCount}`);
      newTaskDetected = true;
      previousCount = currentCount;
    } else {
      console.log(`[${elapsed}s] Task count: ${currentCount} (no change)`);
    }
  }

  console.log('');
  console.log('===================================');
  console.log('RESULTS:');
  console.log(`- Final task count: ${previousCount}`);
  console.log(`- Auto-tasks generated: ${newTaskDetected ? 'YES - ISSUE DETECTED!' : 'NO - OK'}`);
  console.log('===================================');

  // Check what might be creating tasks
  if (newTaskDetected) {
    console.log('');
    console.log('Investigating root cause...');

    // Check if there are any timers or intervals
    const timersInfo = await page.evaluate(() => {
      return {
        hasSetTimeout: !!window.setTimeout,
        hasSetInterval: !!window.setInterval,
      };
    });

    // Check network requests
    const requests = [];
    page.on('request', request => {
      if (request.method() === 'POST' && request.url().includes('/api/tasks')) {
        requests.push({
          url: request.url(),
          method: request.method(),
          time: new Date().toISOString(),
        });
      }
    });

    console.log('Network monitoring for POST /api/tasks requests...');
    await page.waitForTimeout(5000);
    console.log(`POST /api/tasks requests detected: ${requests.length}`);
    requests.forEach(r => console.log(`  - ${r.time}: ${r.method} ${r.url}`));
  }

  await browser.close();
}

investigateAutoTasks().catch(console.error);
