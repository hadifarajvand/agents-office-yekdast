import { chromium } from 'playwright';

(async () => {
  console.log('🎬 PLAYWRIGHT UI INSPECTION TEST\n');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('\n1️⃣  Navigating to http://localhost:4520...');
    await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
    console.log('   ✅ Page loaded');
    
    // Take initial screenshot
    await page.screenshot({ path: '/tmp/ui_load.png' });
    console.log('   📸 Screenshot: ui_load.png');
    
    // Get page title
    const title = await page.title();
    console.log(`   📄 Title: "${title}"`);
    
    // Check for badge counts
    console.log('\n2️⃣  Checking badge counts...');
    const badges = await page.locator('[data-tk]').all();
    console.log(`   Found ${badges.length} badge elements`);
    
    for (const badge of badges) {
      const text = await badge.textContent();
      const dataAttr = await badge.getAttribute('data-tk');
      console.log(`   📊 ${dataAttr}: ${text}`);
    }
    
    // Check for department desks
    console.log('\n3️⃣  Checking department desks...');
    const deptDesks = await page.locator('[data-dept]').all();
    console.log(`   Found ${deptDesks.length} department desks`);
    
    for (const desk of deptDesks) {
      const dept = await desk.getAttribute('data-dept');
      const text = await desk.textContent();
      console.log(`   🏢 Department: ${dept}`);
    }
    
    // Check for task cards
    console.log('\n4️⃣  Checking task cards...');
    const taskCards = await page.locator('[data-task], [data-taskid]').all();
    console.log(`   Found ${taskCards.length} task cards`);
    
    for (let i = 0; i < Math.min(5, taskCards.length); i++) {
      const card = taskCards[i];
      const html = await card.innerHTML();
      const text = await card.textContent();
      console.log(`   📋 Task ${i + 1}: ${text?.substring(0, 50)}...`);
    }
    
    // Check for animations
    console.log('\n5️⃣  Checking for CSS animations...');
    const animatedElements = await page.locator('[class*="anim"], [class*="fade"], [class*="slide"]').all();
    console.log(`   Found ${animatedElements.length} animated elements`);
    
    // Check page structure
    console.log('\n6️⃣  Page structure...');
    const bodyClass = await page.locator('body').getAttribute('class');
    console.log(`   Body class: ${bodyClass}`);
    
    const mainContent = await page.locator('main, [role="main"]').count();
    console.log(`   Main content areas: ${mainContent}`);
    
    // Interaction test - try to click a department
    console.log('\n7️⃣  Testing interactions...');
    const firstDept = await page.locator('[data-dept]').first();
    if (firstDept) {
      const deptName = await firstDept.getAttribute('data-dept');
      console.log(`   🖱️  Clicking department: ${deptName}`);
      await firstDept.click({ timeout: 5000 });
      await page.waitForTimeout(500);
      console.log(`   ✅ Clicked successfully`);
      
      await page.screenshot({ path: '/tmp/ui_after_click.png' });
      console.log(`   📸 Screenshot: ui_after_click.png`);
    }
    
    // Check for real-time data
    console.log('\n8️⃣  Checking real-time data updates...');
    console.log('   Waiting 7 seconds for polling cycle...');
    await page.waitForTimeout(7000);
    
    const updatedBadges = await page.locator('[data-tk]').all();
    console.log(`   After polling: ${updatedBadges.length} badge elements`);
    
    // Final screenshot
    await page.screenshot({ path: '/tmp/ui_final.png' });
    console.log('   📸 Screenshot: ui_final.png');
    
    console.log('\n9️⃣  Checking console for errors...');
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`   ❌ Console Error: ${msg.text()}`);
      }
    });
    
    page.on('pageerror', err => {
      console.log(`   ❌ Page Error: ${err.message}`);
    });
    
    console.log('\n✅ UI INSPECTION COMPLETE');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  } finally {
    await browser.close();
  }
})();
