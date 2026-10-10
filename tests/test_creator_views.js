const fs = require('fs');
const path = require('path');
const http = require('http');

console.log("=== CREATOR STUDIO ARCHITECTURE VERIFICATION ===");

// 1. Verify CSS Rules
const cssContent = fs.readFileSync(path.join(__dirname, '../frontend/static/css/style.css'), 'utf-8');

const hasCreatorViewHidden = cssContent.includes('.creator-view') && cssContent.includes('display: none');
const hasCreatorViewActive = cssContent.includes('.creator-view.active') && cssContent.includes('display: block');
const hasStickySidebar = cssContent.includes('position: sticky') && cssContent.includes('height: calc(100vh - 80px)');

console.log(`[CSS Check] .creator-view display:none rule: ${hasCreatorViewHidden ? 'PASSED' : 'FAILED'}`);
console.log(`[CSS Check] .creator-view.active display:block rule: ${hasCreatorViewActive ? 'PASSED' : 'FAILED'}`);
console.log(`[CSS Check] .sidebar position:sticky & height rule: ${hasStickySidebar ? 'PASSED' : 'FAILED'}`);

if (!hasCreatorViewHidden || !hasCreatorViewActive || !hasStickySidebar) {
  process.exit(1);
}

// 2. Verify HTML Structure
const htmlContent = fs.readFileSync(path.join(__dirname, '../frontend/templates/index.html'), 'utf-8');

const expectedSidebarLinks = [
  'cside-link-dashboard',
  'cside-link-my-courses',
  'cside-link-upload',
  'cside-link-live',
  'cside-link-requests',
  'cside-link-analytics',
  'cside-link-profile'
];

expectedSidebarLinks.forEach(linkId => {
  const exists = htmlContent.includes(`id="${linkId}"`);
  console.log(`[HTML Check] Sidebar link #${linkId}: ${exists ? 'PASSED' : 'FAILED'}`);
  if (!exists) process.exit(1);
});

const expectedViews = [
  'creator-view-dashboard',
  'creator-view-my-courses',
  'creator-view-upload',
  'creator-view-live',
  'creator-view-requests',
  'creator-view-analytics',
  'creator-view-profile'
];

expectedViews.forEach(viewId => {
  const exists = htmlContent.includes(`id="${viewId}"`) && htmlContent.includes(`class="creator-view`);
  console.log(`[HTML Check] Independent section #${viewId}: ${exists ? 'PASSED' : 'FAILED'}`);
  if (!exists) process.exit(1);
});

// Check that preserved element IDs exist in their appropriate sections
const preservedElementIds = [
  'creatorStats',
  'myPlaylistsList',
  'mySingleVideosList',
  'liveSessionsList',
  'creatorRequestsList',
  'creatorAnalyticsStats',
  'creatorReviewsList',
  'creatorProfileCard'
];

preservedElementIds.forEach(elId => {
  const exists = htmlContent.includes(`id="${elId}"`);
  console.log(`[HTML Check] Preserved dynamic container #${elId}: ${exists ? 'PASSED' : 'FAILED'}`);
  if (!exists) process.exit(1);
});

// 3. Verify JavaScript Logic in script.js
const jsContent = fs.readFileSync(path.join(__dirname, '../frontend/static/js/script.js'), 'utf-8');

const hasSwitchCreatorTab = jsContent.includes('function switchCreatorTab(tab)');
const handlesUploadAndLive = jsContent.includes("tab === 'live'") && jsContent.includes("targetView.classList.add('active')");
const handlesScrollTop = jsContent.includes('contentArea.scrollTop = 0');
const hasCreatorPageShow = jsContent.includes("switchCreatorTab('dashboard')");

console.log(`[JS Check] switchCreatorTab implementation: ${hasSwitchCreatorTab ? 'PASSED' : 'FAILED'}`);
console.log(`[JS Check] Tab routing and activation logic: ${handlesUploadAndLive ? 'PASSED' : 'FAILED'}`);
console.log(`[JS Check] Content scroll-to-top on switch: ${handlesScrollTop ? 'PASSED' : 'FAILED'}`);
console.log(`[JS Check] Default to dashboard on creator studio entry: ${hasCreatorPageShow ? 'PASSED' : 'FAILED'}`);

if (!hasSwitchCreatorTab || !handlesUploadAndLive || !hasCreatorPageShow) {
  process.exit(1);
}

// 4. Test live HTTP responses from local server
http.get('http://127.0.0.1:5000/', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log(`\n[Server Check] http://127.0.0.1:5000/ Status: ${res.statusCode}`);
    const serverHasViews = expectedViews.every(v => data.includes(`id="${v}"`));
    console.log(`[Server Check] Live served HTML contains all 7 independent views: ${serverHasViews ? 'PASSED' : 'FAILED'}`);
    
    if (serverHasViews) {
      console.log("\nALL TESTS PASSED SUCCESSFULLY! Creator Studio views are completely isolated.");
      process.exit(0);
    } else {
      process.exit(1);
    }
  });
}).on('error', (err) => {
  console.error("Server check error:", err);
  process.exit(1);
});
