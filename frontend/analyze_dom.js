import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:4520', { waitUntil: 'networkidle' });
  
  // Get detailed DOM info
  const domInfo = await page.evaluate(() => {
    const info = {
      page_title: document.title,
      body_html_length: document.body.innerHTML.length,
      main_container: document.querySelector('main')?.id || document.querySelector('[role="main"]')?.id || 'none',
      panel_sections: [],
      agent_cards: [],
      task_rows: [],
      all_data_attrs: []
    };
    
    // Find all elements with data attributes
    const allElements = document.querySelectorAll('[data-*]');
    allElements.forEach(el => {
      Array.from(el.attributes).forEach(attr => {
        if (attr.name.startsWith('data-')) {
          info.all_data_attrs.push(attr.name);
        }
      });
    });
    info.all_data_attrs = [...new Set(info.all_data_attrs)];
    
    // Find task panel sections
    const panels = document.querySelectorAll('[class*="panel"], [class*="section"], [role="tabpanel"]');
    info.panel_sections = Array.from(panels).map(p => ({
      class: p.className,
      text: p.textContent?.substring(0, 100)
    }));
    
    // Find agent/task rows
    const rows = document.querySelectorAll('[data-id], [data-agent], [data-task]');
    info.agent_cards = Array.from(rows).slice(0, 10).map(r => ({
      id: r.getAttribute('data-id'),
      agent: r.getAttribute('data-agent'),
      task: r.getAttribute('data-task'),
      class: r.className,
      text: r.textContent?.substring(0, 80)
    }));
    
    return info;
  });
  
  console.log('🔍 DOM ANALYSIS:');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('\n📄 Page Title:', domInfo.page_title);
  console.log('📝 Body HTML length:', domInfo.body_html_length, 'bytes');
  
  console.log('\n🏷️  All data attributes found:');
  domInfo.all_data_attrs.forEach(attr => {
    console.log(`   • ${attr}`);
  });
  
  console.log('\n📊 Agent/Task rows (first 10):');
  domInfo.agent_cards.forEach((card, i) => {
    console.log(`\n   Row ${i + 1}:`);
    console.log(`      ID: ${card.id}`);
    console.log(`      Agent: ${card.agent}`);
    console.log(`      Class: ${card.class}`);
    console.log(`      Text: ${card.text}`);
  });
  
  console.log('\n✅ DOM INSPECTION COMPLETE');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  
  await browser.close();
})();
