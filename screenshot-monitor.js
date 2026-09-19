import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

async function screenshotMonitor() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  const screenshotDir = './screenshots';
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  console.log('');
  console.log('LIVE SCREENSHOT MONITORING - Watching for Auto-Generated Tasks');
  console.log('================================================================');
  console.log('');
  console.log('Taking screenshots every 2 seconds for 60 seconds...');
  console.log('');

  let taskHistory = [];
  let screenshotCount = 0;

  page.on('response', response => {
    if (response.url().includes('/api/tasks')) {
      response.json().then(tasks => {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] API /api/tasks returned ${tasks.length} tasks`);

        // Log task details
        if (tasks.length > 0) {
          tasks.forEach((t, idx) => {
            console.log(`    ${idx + 1}. "${t.title}" - Agent: ${t.agent} - State: ${t.state}`);
          });
        }
      }).catch(() => {});
    }
  });

  console.log('Opening Agent Office UI...');
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Take initial screenshot
  console.log('');
  console.log('Starting observation period...');
  console.log('');

  const startTime = Date.now();
  let previousTaskCount = 0;

  while (Date.now() - startTime < 60000) {
    screenshotCount++;
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const timestamp = new Date().toLocaleTimeString();

    // Take screenshot
    const screenshotPath = path.join(screenshotDir, `screenshot-${elapsed}s-${timestamp.replace(/:/g, '-')}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });

    // Get current task count from UI
    const currentTasks = await page.evaluate(() => {
      const taskCards = document.querySelectorAll('[data-task-id]');
      const tasks = Array.from(taskCards).map(card => {
        return {
          id: card.getAttribute('data-task-id'),
          title: card.querySelector('.tt')?.textContent || 'Unknown',
          state: card.getAttribute('data-state') || 'Unknown'
        };
      });
      return tasks;
    });

    if (currentTasks.length !== previousTaskCount) {
      console.log(`[${timestamp}] ⚠️  TASK COUNT CHANGED: ${previousTaskCount} → ${currentTasks.length}`);
      console.log(`    Screenshot saved: ${screenshotPath}`);

      // Show new tasks
      if (currentTasks.length > previousTaskCount) {
        console.log(`    New tasks appeared:`);
        currentTasks.forEach((t, idx) => {
          console.log(`      ${idx + 1}. "${t.title}" [${t.state}]`);
        });
      }

      previousTaskCount = currentTasks.length;
    } else {
      console.log(`[${timestamp}] Task count stable: ${currentTasks.length}`);
    }

    await page.waitForTimeout(2000);
  }

  console.log('');
  console.log('================================================================');
  console.log(`MONITORING COMPLETE - ${screenshotCount} screenshots taken`);
  console.log(`Screenshots saved to: ${path.resolve(screenshotDir)}`);
  console.log('================================================================');
  console.log('');

  // Show all screenshots for review
  const files = fs.readdirSync(screenshotDir);
  console.log(`Total screenshots: ${files.length}`);
  files.forEach(f => console.log(`  - ${f}`));
  console.log('');

  // Keep browser open for 5 more seconds so user can see final state
  console.log('Browser will close in 5 seconds...');
  await page.waitForTimeout(5000);

  await browser.close();
}

screenshotMonitor().catch(console.error);
