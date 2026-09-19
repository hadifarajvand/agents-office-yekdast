import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
  
  console.log('🔍 DETAILED UI INSPECTION');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  
  // Check what's actually being displayed
  const uiState = await page.evaluate(() => {
    const info = {
      page_title: document.title,
      h1_text: document.querySelector('h1')?.textContent || 'none',
      visible_text_sample: document.body.textContent?.substring(0, 200),
      
      // Count different element types
      buttons: document.querySelectorAll('button').length,
      panels: document.querySelectorAll('[class*="panel"]').length,
      rows: document.querySelectorAll('[class*="row"]').length,
      
      // Check specific selectors
      doing_tasks: Array.from(document.querySelectorAll('.doing, [class*="doing"]')).length,
      next_tasks: Array.from(document.querySelectorAll('.next, [class*="next"]')).length,
      done_tasks: Array.from(document.querySelectorAll('.done, [class*="done"]')).length,
      
      // Sample text from visible elements
      visible_elements: Array.from(document.querySelectorAll('div, span, h2, h3'))
        .filter(el => el.textContent?.length > 5 && el.textContent?.length < 100)
        .map(el => el.textContent?.trim())
        .filter((t, i) => i < 20)
    };
    return info;
  });
  
  console.log('📄 Page Title:', uiState.page_title);
  console.log('\n📊 Element counts:');
  console.log(`   Buttons: ${uiState.buttons}`);
  console.log(`   Panels: ${uiState.panels}`);
  console.log(`   Rows: ${uiState.rows}`);
  console.log(`   DOING elements: ${uiState.doing_tasks}`);
  console.log(`   NEXT elements: ${uiState.next_tasks}`);
  console.log(`   DONE elements: ${uiState.done_tasks}`);
  
  console.log('\n📝 Visible text samples:');
  uiState.visible_elements.slice(0, 15).forEach(text => {
    if (text) console.log(`   • ${text}`);
  });
  
  // Try to find the main interface
  console.log('\n🎯 Looking for main UI sections...');
  const sections = await page.locator('div').evaluateAll(divs => {
    return divs
      .filter(d => d.textContent && d.textContent.length > 50 && d.textContent.length < 500)
      .map(d => ({
        class: d.className,
        text: d.textContent.substring(0, 80)
      }))
      .slice(0, 10);
  });
  
  sections.forEach((s, i) => {
    console.log(`   ${i + 1}. [${s.class}] ${s.text}`);
  });
  
  // Screenshot for visual inspection
  console.log('\n📸 Taking screenshot...');
  await page.screenshot({ path: 'C:/Users/EndWay/AppData/Local/Temp/claude/ui-screenshot.png' });
  console.log('   ✅ Saved to: C:/Users/EndWay/AppData/Local/Temp/claude/ui-screenshot.png');
  
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  
  await browser.close();
})();
