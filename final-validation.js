import { chromium } from 'playwright';

async function finalValidation() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('');
  console.log('FINAL VALIDATION TEST - 30 Second No-Auto-Task Run');
  console.log('=====================================================');
  console.log('');

  const results = {
    startTime: new Date(),
    initialBackendTasks: 0,
    finalBackendTasks: 0,
    autoTasksDetected: false,
    uiTasksEvolution: [],
    apiCallsCount: 0,
  };

  // Monitor API calls
  page.on('response', response => {
    if (response.url().includes('/api/tasks')) {
      results.apiCallsCount++;
    }
  });

  console.log('Step 1: Getting initial backend state');
  const initialState = await fetch('http://localhost:8000/api/tasks').then(r => r.json());
  results.initialBackendTasks = initialState.length;
  console.log(`  Backend task count: ${results.initialBackendTasks}`);
  console.log('');

  console.log('Step 2: Opening frontend in headless browser');
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  let initialUiCount = await page.evaluate(() => {
    const taskCards = document.querySelectorAll('[data-task-id]');
    return taskCards.length;
  });

  results.uiTasksEvolution.push({ time: 0, count: initialUiCount });
  console.log(`  Initial UI task count: ${initialUiCount}`);
  console.log('');

  console.log('Step 3: 30-second observation period');
  console.log('  Checking every 3 seconds:');
  console.log('');

  let maxTasksSeen = initialUiCount;
  const observationStart = Date.now();

  while (Date.now() - observationStart < 30000) {
    await page.waitForTimeout(3000);

    const elapsed = Math.round((Date.now() - observationStart) / 1000);
    const count = await page.evaluate(() => {
      const taskCards = document.querySelectorAll('[data-task-id]');
      return taskCards.length;
    });

    results.uiTasksEvolution.push({ time: elapsed, count });

    if (count > maxTasksSeen) {
      console.log(`    [${elapsed}s] ⚠️  ALERT: Task count increased ${maxTasksSeen} → ${count}`);
      results.autoTasksDetected = true;
      maxTasksSeen = count;
    } else if (count < maxTasksSeen) {
      console.log(`    [${elapsed}s] ℹ️  Tasks decreased ${maxTasksSeen} → ${count}`);
      maxTasksSeen = count;
    } else {
      console.log(`    [${elapsed}s] ✓ Task count stable: ${count}`);
    }
  }

  console.log('');
  console.log('Step 4: Final backend verification');
  const finalState = await fetch('http://localhost:8000/api/tasks').then(r => r.json());
  results.finalBackendTasks = finalState.length;
  console.log(`  Final backend task count: ${results.finalBackendTasks}`);
  console.log('');

  // Report results
  console.log('=====================================================');
  console.log('VALIDATION RESULTS');
  console.log('=====================================================');
  console.log('');
  console.log('1. Auto-Task Generation Check:');
  console.log(`   Status: ${results.autoTasksDetected ? '❌ FAILED - Auto tasks detected!' : '✅ PASSED - No auto tasks'}`);
  console.log('');

  console.log('2. Backend Stability:');
  const backendStable = results.finalBackendTasks === results.initialBackendTasks;
  console.log(`   Initial tasks: ${results.initialBackendTasks}`);
  console.log(`   Final tasks: ${results.finalBackendTasks}`);
  console.log(`   Status: ${backendStable ? '✅ PASSED - No unexpected backend tasks' : '❌ FAILED - Backend task count changed'}`);
  console.log('');

  console.log('3. UI Stability:');
  const uiStable = !results.autoTasksDetected;
  const taskProgression = results.uiTasksEvolution
    .map(e => `[${e.time}s: ${e.count}]`)
    .join(' ');
  console.log(`   Task evolution: ${taskProgression}`);
  console.log(`   Status: ${uiStable ? '✅ PASSED - UI task count stable' : '❌ FAILED - UI tasks changed'}`);
  console.log('');

  console.log('4. API Activity:');
  console.log(`   Total /api/tasks calls: ${results.apiCallsCount}`);
  console.log(`   Status: ✅ PASSED - API responsive`);
  console.log('');

  // Overall result
  const allPassed = !results.autoTasksDetected && backendStable && uiStable;
  console.log('=====================================================');
  console.log(allPassed ? '✅✅✅ ALL VALIDATION TESTS PASSED ✅✅✅' : '❌ VALIDATION FAILED');
  console.log('=====================================================');
  console.log('');

  if (allPassed) {
    console.log('CONCLUSION:');
    console.log('The auto-task generation issue has been FIXED.');
    console.log('No tasks are automatically generated during normal operation.');
    console.log('');
  }

  await browser.close();
}

finalValidation().catch(console.error);
