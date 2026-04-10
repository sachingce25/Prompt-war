/**
 * VenueFlow — Frontend Application Logic
 * Handles tabs, data fetching, SVG map, chat, parking, and planner.
 */

// ============================================================
// CONSTANTS & STATE
// ============================================================
const API_BASE = '';
const REFRESH_INTERVAL = 30000; // 30 seconds

// ============================================================
// GOOGLE ANALYTICS 4 — Event Tracking Helpers
// ============================================================
/**
 * Fire a GA4 custom event. Gracefully no-ops if gtag is not loaded.
 * @param {string} eventName - GA4 event name
 * @param {Object} params    - Event parameters
 */
function trackEvent(eventName, params = {}) {
  if (typeof gtag === 'function') {
    gtag('event', eventName, params);
  }
}

let crowdData = null;
let waitData = null;
let parkingData = null;
let chatBusy = false;
let planEvents = [
  { id: 1, type: 'match', time: '18:00', title: 'Gates Open', desc: 'Arrive early for best experience', done: false },
  { id: 2, type: 'food', time: '18:30', title: 'Pre-game Snack', desc: 'Burger Blitz — Section A', done: false },
  { id: 3, type: 'restroom', time: '19:00', title: 'Restroom Break', desc: 'Use Restroom E-F (shortest wait)', done: true },
  { id: 4, type: 'match', time: '19:15', title: 'Kickoff!', desc: 'Championship Finals begin', done: false },
  { id: 5, type: 'food', time: '20:00', title: 'Halftime Food', desc: 'Noodle Bar — Section E', done: false },
  { id: 6, type: 'alert', time: '21:30', title: 'Prepare to Exit', desc: 'Head to Zone D parking', done: false },
];
let nextEventId = 7;

// Zone metadata (for map popups)
const ZONE_META = {
  A: { exit: 'Gate 1', food: 'Burger Blitz', restroom: 'Restroom A-B' },
  B: { exit: 'Gate 1', food: 'Hydration Station', restroom: 'Restroom A-B' },
  C: { exit: 'Gate 2', food: 'Taco Fiesta', restroom: 'Restroom C-D' },
  D: { exit: 'Gate 2', food: 'Hydration Station', restroom: 'Restroom C-D' },
  E: { exit: 'Gate 3', food: 'Noodle Bar', restroom: 'Restroom E-F' },
  F: { exit: 'Gate 3', food: 'Hydration Station', restroom: 'Restroom E-F' },
  G: { exit: 'Gate 4', food: 'Pizza Planet', restroom: 'Restroom G-H' },
  H: { exit: 'Gate 4', food: 'Hydration Station', restroom: 'Restroom G-H' },
};

// ============================================================
// UTILITY
// ============================================================
function statusColor(s) {
  return s === 'low' ? 'var(--cool)' : s === 'moderate' ? 'var(--warm)' : 'var(--hot)';
}
function statusClass(s) {
  return s === 'low' ? 'low' : s === 'moderate' ? 'moderate' : 'high';
}
function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(msg, type = 'info', duration = 4000) {
  const ct = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${msg}</span>`;
  ct.appendChild(t);
  setTimeout(() => { t.classList.add('removing'); setTimeout(() => t.remove(), 300); }, duration);
}

// ============================================================
// TAB SWITCHING  (click + keyboard arrow navigation)
// ============================================================
const tabBtns = Array.from(document.querySelectorAll('.tab-btn'));

function activateTab(btn) {
  tabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); b.tabIndex = -1; });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  btn.setAttribute('aria-selected', 'true');
  btn.tabIndex = 0;
  btn.focus();
  const panel = document.getElementById('panel-' + btn.dataset.tab);
  if (panel) panel.classList.add('active');
  if (btn.dataset.tab === 'map' && crowdData) renderFullMap(crowdData);
  // GA4: track tab navigation
  trackEvent('tab_view', { tab_name: btn.dataset.tab, event_category: 'navigation' });
}

tabBtns.forEach((btn, idx) => {
  btn.tabIndex = idx === 0 ? 0 : -1;
  btn.addEventListener('click', () => activateTab(btn));
  btn.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') { activateTab(tabBtns[(idx + 1) % tabBtns.length]); e.preventDefault(); }
    if (e.key === 'ArrowLeft')  { activateTab(tabBtns[(idx - 1 + tabBtns.length) % tabBtns.length]); e.preventDefault(); }
    if (e.key === 'Home') { activateTab(tabBtns[0]); e.preventDefault(); }
    if (e.key === 'End')  { activateTab(tabBtns[tabBtns.length - 1]); e.preventDefault(); }
  });
});

// ============================================================
// DATA FETCHING
// ============================================================
async function fetchCrowdData() {
  try {
    const r = await fetch(`${API_BASE}/api/crowd`);
    crowdData = await r.json();
    renderDashboard();
    return crowdData;
  } catch (e) { console.error('Crowd fetch error:', e); }
}

async function fetchWaitData() {
  try {
    const r = await fetch(`${API_BASE}/api/waits`);
    waitData = await r.json();
    renderWaits();
    // Process alerts
    if (waitData.alerts) {
      waitData.alerts.forEach(a => showToast(`⚡ ${a.message}`, 'success'));
    }
    return waitData;
  } catch (e) { console.error('Wait fetch error:', e); }
}

async function fetchParkingData() {
  try {
    const r = await fetch(`${API_BASE}/api/parking`);
    parkingData = await r.json();
    renderParking();
    return parkingData;
  } catch (e) { console.error('Parking fetch error:', e); }
}

async function fetchAll() {
  await Promise.all([fetchCrowdData(), fetchWaitData(), fetchParkingData()]);
}

// ============================================================
// DASHBOARD RENDER
// ============================================================
function renderDashboard() {
  if (!crowdData) return;
  const zones = crowdData.zones;
  const densities = Object.values(zones).map(z => z.density);
  const avg = Math.round(densities.reduce((a, b) => a + b, 0) / densities.length);
  document.getElementById('avgCrowd').textContent = avg + '%';

  // Fastest gate from wait data
  if (waitData) {
    const gates = waitData.waits.gates;
    const best = gates.reduce((a, b) => a.wait < b.wait ? a : b);
    document.getElementById('fastGate').textContent = best.wait + 'm';
    document.getElementById('fastGateSub').textContent = best.name;
    document.getElementById('alertCount').textContent = waitData.alerts ? waitData.alerts.length : '0';
  }

  // Render mini map in dashboard
  renderMiniMap(zones);
}

// ============================================================
// WAIT TIMES RENDER
// ============================================================
function renderWaits() {
  if (!waitData) return;
  const ct = document.getElementById('dashWaits');
  const icons = { gates: '🚪', food: '🍔', restrooms: '🚻', parking: '🚗' };
  let html = '';
  for (const [cat, items] of Object.entries(waitData.waits)) {
    items.forEach(it => {
      const pct = Math.min(100, (it.wait / 30) * 100);
      const col = statusColor(it.status);
      html += `<div class="wait-item">
        <div class="wait-icon">${icons[cat] || '⏱️'}</div>
        <div class="wait-info">
          <div class="wait-name">${it.name}</div>
          <div class="wait-bar-bg"><div class="wait-bar" style="width:${pct}%;background:${col}"></div></div>
        </div>
        <div class="wait-time ${statusClass(it.status)}">${it.wait}m</div>
      </div>`;
    });
  }
  ct.innerHTML = html;
}

// ============================================================
// SVG STADIUM MAP
// ============================================================
function buildStadiumSVG(zones, full = false) {
  const w = 700, h = 500, cx = 350, cy = 250, rx = 280, ry = 200;
  // Zone positions (8 sections around the oval)
  const angles = [
    { z: 'A', a: -90 },  { z: 'B', a: -45 },
    { z: 'C', a: 0 },    { z: 'D', a: 45 },
    { z: 'E', a: 90 },   { z: 'F', a: 135 },
    { z: 'G', a: 180 },  { z: 'H', a: -135 },
  ];
  const gatePositions = [
    { label: 'Gate 1', x: cx, y: cy - ry - 20 },
    { label: 'Gate 2', x: cx + rx + 20, y: cy },
    { label: 'Gate 3', x: cx, y: cy + ry + 20 },
    { label: 'Gate 4', x: cx - rx - 20, y: cy },
  ];
  const facilities = [
    { icon: '🍔', x: cx - 120, y: cy - 90, label: 'Burger Blitz' },
    { icon: '🌮', x: cx + 140, y: cy - 40, label: 'Taco Fiesta' },
    { icon: '🍜', x: cx + 40, y: cy + 80, label: 'Noodle Bar' },
    { icon: '🍕', x: cx - 140, y: cy + 40, label: 'Pizza Planet' },
  ];
  const restrooms = [
    { x: cx - 50, y: cy - 110 }, { x: cx + 130, y: cy + 30 },
    { x: cx + 40, y: cy + 110 }, { x: cx - 130, y: cy - 10 },
  ];

  let svg = `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Apex Arena venue map showing crowd density by section">`;
  // Outer stadium
  svg += `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="2"/>`;
  svg += `<ellipse cx="${cx}" cy="${cy}" rx="${rx - 30}" ry="${ry - 25}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1.5"/>`;
  // Field
  svg += `<ellipse cx="${cx}" cy="${cy}" rx="${rx - 90}" ry="${ry - 70}" fill="rgba(34,229,160,0.06)" stroke="rgba(34,229,160,0.15)" stroke-width="1"/>`;
  svg += `<text x="${cx}" y="${cy + 5}" text-anchor="middle" fill="rgba(255,255,255,0.2)" font-size="14" font-weight="700">FIELD</text>`;

  // Zone sections
  angles.forEach(({ z, a }) => {
    const rad = (a * Math.PI) / 180;
    const zx = cx + (rx - 55) * Math.cos(rad);
    const zy = cy + (ry - 45) * Math.sin(rad);
    const d = zones[z] ? zones[z].density : 50;
    const s = zones[z] ? zones[z].status : 'moderate';
    const col = s === 'low' ? 'var(--cool)' : s === 'moderate' ? 'var(--warm)' : 'var(--hot)';
    const fillCol = s === 'low' ? 'rgba(34,229,160,' : s === 'moderate' ? 'rgba(255,170,0,' : 'rgba(255,92,56,';

    // Pulsing circle
    if (s === 'high') {
      svg += `<circle cx="${zx}" cy="${zy}" r="18" fill="${fillCol}0.12)" stroke="${fillCol}0.3)" stroke-width="1">
        <animate attributeName="r" values="18;28;18" dur="2s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.7;0.2;0.7" dur="2s" repeatCount="indefinite"/>
      </circle>`;
    }
    svg += `<circle cx="${zx}" cy="${zy}" r="24" fill="${fillCol}0.2)" stroke="${col}" stroke-width="1.5"
      style="cursor:pointer" data-zone="${z}" class="zone-circle"/>`;
    svg += `<text x="${zx}" y="${zy - 6}" text-anchor="middle" fill="white" font-size="13" font-weight="800" pointer-events="none">${z}</text>`;
    svg += `<text x="${zx}" y="${zy + 10}" text-anchor="middle" fill="${col}" font-size="10" font-weight="600" pointer-events="none">${d}%</text>`;
  });

  // Gates
  gatePositions.forEach(g => {
    svg += `<circle cx="${g.x}" cy="${g.y}" r="8" fill="var(--accent)" opacity="0.8"/>`;
    const ty = g.y < cy ? g.y - 14 : g.y + 18;
    svg += `<text x="${g.x}" y="${ty}" text-anchor="middle" fill="var(--accent2)" font-size="10" font-weight="700">${g.label}</text>`;
  });

  if (full) {
    // Food icons
    facilities.forEach(f => {
      svg += `<text x="${f.x}" y="${f.y}" text-anchor="middle" font-size="16" style="cursor:help"><title>${f.label}</title>${f.icon}</text>`;
    });
    // Restroom icons
    restrooms.forEach(r => {
      svg += `<text x="${r.x}" y="${r.y}" text-anchor="middle" font-size="12" fill="#a855f7">🚻</text>`;
    });
  }
  svg += '</svg>';
  return svg;
}

function renderMiniMap(zones) {
  document.getElementById('dashMap').innerHTML = buildStadiumSVG(zones, false);
  attachMapListeners('dashMap');
}

function renderFullMap(data) {
  document.getElementById('mapSvgContainer').innerHTML = buildStadiumSVG(data.zones, true);
  attachMapListeners('mapSvgContainer');
}

function attachMapListeners(containerId) {
  const ct = document.getElementById(containerId);
  ct.querySelectorAll('.zone-circle').forEach(el => {
    el.addEventListener('mouseenter', e => showMapPopup(e, el.dataset.zone));
    el.addEventListener('mouseleave', () => hideMapPopup());
    el.addEventListener('click', e => showMapPopup(e, el.dataset.zone));
    el.addEventListener('focus', e => showMapPopup(e, el.dataset.zone));
  });
}

function showMapPopup(e, zone) {
  if (!crowdData) return;
  const popup = document.getElementById('mapPopup');
  const z = crowdData.zones[zone];
  const meta = ZONE_META[zone];
  document.getElementById('popupTitle').textContent = `Section ${zone}`;
  document.getElementById('popupCrowd').textContent = z.density + '%';
  document.getElementById('popupCrowd').style.color = statusColor(z.status);
  document.getElementById('popupStatus').textContent = z.status.charAt(0).toUpperCase() + z.status.slice(1);
  document.getElementById('popupExit').textContent = meta.exit;
  // Get wait from waitData if available
  let waitStr = '—';
  if (waitData) {
    const gateName = meta.exit;
    const gate = waitData.waits.gates.find(g => g.name.includes(gateName.split(' ')[1]));
    if (gate) waitStr = gate.wait + ' min';
  }
  document.getElementById('popupWait').textContent = waitStr;
  const rect = e.target.getBoundingClientRect();
  const mapRect = document.getElementById('fullMap')?.getBoundingClientRect() || document.getElementById('dashMap').parentElement.getBoundingClientRect();
  popup.style.left = (rect.left - mapRect.left + 30) + 'px';
  popup.style.top = (rect.top - mapRect.top - 20) + 'px';
  popup.classList.add('show');
}

function hideMapPopup() {
  document.getElementById('mapPopup').classList.remove('show');
}

// ============================================================
// AI CHAT
// ============================================================
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');
const chatMessages = document.getElementById('chatMessages');

async function sendChat(msg) {
  if (!msg.trim() || chatBusy) return;
  chatBusy = true;
  // GA4: track AI concierge usage
  trackEvent('ai_concierge_query', { query_length: msg.length, event_category: 'engagement' });
  // User message
  appendMsg(msg, 'user');
  chatInput.value = '';
  // Typing indicator
  const typing = document.createElement('div');
  typing.className = 'typing-indicator';
  typing.innerHTML = '<span></span><span></span><span></span>';
  chatMessages.appendChild(typing);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const r = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg }),
    });
    const data = await r.json();
    typing.remove();
    if (data.reply) {
      appendMsg(data.reply, 'ai');
    } else {
      appendMsg('Sorry, I couldn\'t process that. Try again!', 'ai');
    }
  } catch (e) {
    typing.remove();
    appendMsg('Connection error. Please try again.', 'ai');
  }
  chatBusy = false;
}

function appendMsg(text, role) {
  const d = document.createElement('div');
  d.className = `msg ${role}`;
  // Simple markdown-like bold
  d.innerHTML = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  chatMessages.appendChild(d);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatSend.addEventListener('click', () => sendChat(chatInput.value));
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(chatInput.value); });

// Quick action chips (now semantic <button> elements)
document.querySelectorAll('.chip[data-msg]').forEach(chip => {
  chip.addEventListener('click', () => {
    sendChat(chip.dataset.msg);
    // Switch to concierge tab if not already active
    const conciergeBtn = document.querySelector('[data-tab="concierge"]');
    if (conciergeBtn && !conciergeBtn.classList.contains('active')) activateTab(conciergeBtn);
  });
});

// ============================================================
// PARKING RENDER
// ============================================================
function renderParking() {
  if (!parkingData) return;
  const grid = document.getElementById('parkingGrid');
  let html = '';
  const yourZone = 'D';

  for (const [z, info] of Object.entries(parkingData.zones)) {
    const pct = info.occupancy_pct;
    const col = info.status === 'low' ? 'var(--cool)' : info.status === 'moderate' ? 'var(--warm)' : 'var(--hot)';
    const circumference = 2 * Math.PI * 50;
    const offset = circumference - (circumference * pct / 100);

    html += `<div class="parking-card glass">
      ${z === yourZone ? '<span class="zone-badge">YOUR ZONE</span>' : ''}
      <div class="ring-container">
        <svg viewBox="0 0 120 120">
          <circle class="ring-bg" cx="60" cy="60" r="50"/>
          <circle class="ring-fill" cx="60" cy="60" r="50" stroke="${col}"
            stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
            style="--ring-full:${circumference};--ring-offset:${offset};animation:ringProgress 1.2s ease forwards"/>
        </svg>
        <div class="ring-label">
          <div class="ring-pct" style="color:${col}">${pct}%</div>
          <div class="ring-sub">occupied</div>
        </div>
      </div>
      <div class="p-name">Zone ${z}</div>
      <div class="p-exit">Exit in ~${info.exit_time} min</div>
      <div style="font-size:.7rem;color:var(--muted);margin-top:4px;">${info.occupied}/${info.capacity} spaces</div>
    </div>`;
  }
  grid.innerHTML = html;

  // Exit timeline
  const tl = document.getElementById('exitTimeline');
  let tlHtml = '';
  parkingData.stagger_plan.forEach(step => {
    const col = step.zone === 'D' ? 'var(--cool)' : step.zone === 'A' ? 'var(--hot)' : 'var(--warm)';
    tlHtml += `<div class="exit-step">
      <div class="exit-dot" style="background:rgba(255,255,255,0.05);border-color:${col};color:${col}">${step.zone}</div>
      <div class="exit-label">${step.suggested_exit}</div>
      <div class="exit-time">${step.reason}</div>
    </div>`;
  });
  tl.innerHTML = tlHtml;
}

// ============================================================
// QR CODE GENERATOR
// ============================================================
function drawQR() {
  const canvas = document.getElementById('qrCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const size = 156, modules = 21, cellSize = Math.floor(size / modules);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, size, size);
  // Simulated QR pattern (deterministic from seed)
  const seed = 42;
  let rng = seed;
  function next() { rng = (rng * 1103515245 + 12345) & 0x7fffffff; return rng; }

  ctx.fillStyle = '#000';
  // Position patterns (3 corners)
  function drawFinder(ox, oy) {
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) {
      if (y === 0 || y === 6 || x === 0 || x === 6 || (y >= 2 && y <= 4 && x >= 2 && x <= 4)) {
        ctx.fillRect(ox + x * cellSize, oy + y * cellSize, cellSize, cellSize);
      }
    }
  }
  drawFinder(0, 0);
  drawFinder((modules - 7) * cellSize, 0);
  drawFinder(0, (modules - 7) * cellSize);

  // Random data modules
  for (let y = 0; y < modules; y++) for (let x = 0; x < modules; x++) {
    if ((x < 8 && y < 8) || (x >= modules - 8 && y < 8) || (x < 8 && y >= modules - 8)) continue;
    if (next() % 3 !== 0) ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
  }
}

// ============================================================
// MY PLAN / TIMELINE
// ============================================================
function renderTimeline() {
  const ct = document.getElementById('timeline');
  const icons = { food: '🍔', restroom: '🚻', alert: '⚠️', match: '🏟️' };
  const sorted = [...planEvents].sort((a, b) => a.time.localeCompare(b.time));
  let html = '';
  sorted.forEach(ev => {
    html += `<div class="tl-item">
      <div class="tl-dot ${ev.type}">${icons[ev.type] || '📌'}</div>
      <div class="tl-content">
        <div class="tl-time">${ev.time}</div>
        <div class="tl-title">${ev.title}</div>
        <div class="tl-desc">${ev.desc}</div>
      </div>
      <button class="tl-check ${ev.done ? 'done' : ''}" data-id="${ev.id}" aria-label="Mark ${ev.title} as ${ev.done ? 'not done' : 'done'}">
        ${ev.done ? '✓' : ''}
      </button>
    </div>`;
  });
  ct.innerHTML = html;

  // Toggle done state
  ct.querySelectorAll('.tl-check').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.dataset.id);
      const ev = planEvents.find(e => e.id === id);
      if (ev) { ev.done = !ev.done; renderTimeline(); }
    });
  });
}

// Add reminder
document.getElementById('addReminderBtn').addEventListener('click', () => {
  const type = document.getElementById('reminderType').value;
  const time = document.getElementById('reminderTime').value;
  const title = document.getElementById('reminderTitle').value.trim();
  if (!title) { showToast('Please enter a title', 'warning'); return; }

  planEvents.push({ id: nextEventId++, type, time, title, desc: 'Custom reminder', done: false });
  renderTimeline();
  document.getElementById('reminderTitle').value = '';
  showToast(`✅ Added "${title}" at ${time}`, 'success');

  // Update notification count
  const countEl = document.getElementById('notifCount');
  countEl.textContent = parseInt(countEl.textContent) + 1;
});

// ============================================================
// NOTIFICATION BELL
// ============================================================
document.getElementById('notifBell').addEventListener('click', () => {
  showToast('🔔 3 upcoming events in your timeline', 'info');
});

// ============================================================
// GOOGLE SERVICES — Maps JavaScript API
// ============================================================
let googleMapInstance = null;

async function initGoogleMap() {
  try {
    const r = await fetch(`${API_BASE}/api/maps-config`);
    const cfg = await r.json();
    if (!cfg.enabled || !cfg.api_key) {
      document.getElementById('googleMap').innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:.85rem;">📍 Maps API key not configured</div>';
      return;
    }

    // Dynamically load the Maps JS API
    window.__venueflowMapCallback = function () {
      const { lat, lng, zoom, name } = cfg.venue;
      const mapDiv = document.getElementById('googleMap');
      if (!mapDiv) return;

      googleMapInstance = new google.maps.Map(mapDiv, {
        center: { lat, lng },
        zoom,
        mapTypeId: 'satellite',
        disableDefaultUI: false,
        styles: [
          { elementType: 'geometry', stylers: [{ color: '#0d1325' }] },
          { elementType: 'labels.text.fill', stylers: [{ color: '#8a9bb0' }] },
          { elementType: 'labels.text.stroke', stylers: [{ color: '#050810' }] },
          { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1a2540' }] },
          { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0a1628' }] },
        ],
      });

      new google.maps.Marker({
        position: { lat, lng },
        map: googleMapInstance,
        title: name,
        animation: google.maps.Animation.DROP,
        label: { text: '🏟', fontSize: '24px' },
      });

      const infoWindow = new google.maps.InfoWindow({
        content: `<div style="font-family:Inter,sans-serif;color:#0d1325;padding:4px 8px;">
          <strong>Apex Arena</strong><br>Championship Finals Venue<br>
          <span style="color:#4361ff;font-size:.75rem;">VenueFlow Smart Venue</span>
        </div>`,
      });
      googleMapInstance.addListener('click', () => infoWindow.open(googleMapInstance));

      trackEvent('google_map_loaded', { event_category: 'google_services', map_type: 'satellite' });
    };

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${cfg.api_key}&callback=__venueflowMapCallback&loading=async&libraries=marker`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
  } catch (e) {
    console.warn('[VenueFlow] Could not initialize Google Maps:', e);
  }
}

// ============================================================
// GOOGLE SERVICES — Gemini Status Check
// ============================================================
async function checkGeminiStatus() {
  try {
    const r = await fetch(`${API_BASE}/api/google-services`);
    const data = await r.json();
    const gemini = data.services.find(s => s.name.includes('Gemini'));
    const isActive = gemini && gemini.status === 'active';

    // Update header chip
    const chip = document.getElementById('geminiStatusChip');
    if (chip) chip.classList.toggle('active', isActive);

    // Update concierge indicator
    const dot = document.getElementById('geminiDot');
    const txt = document.getElementById('geminiStatusText');
    if (dot) dot.classList.toggle('active', isActive);
    if (txt) txt.textContent = isActive ? 'Gemini Active' : 'Fallback Mode';

    // Update My Plan card badge
    const badge = document.getElementById('geminiCardBadge');
    if (badge) {
      badge.textContent = isActive ? 'Active' : 'Set API Key';
      badge.classList.toggle('active', isActive);
    }

    // GA4: track Google Services status
    trackEvent('google_services_loaded', { gemini_active: isActive, total_active: data.active, event_category: 'google_services' });
  } catch (e) {
    console.warn('[VenueFlow] Could not fetch Google Services status:', e);
  }
}

// ============================================================
// INITIALIZATION
// ============================================================
(async function init() {
  // Show skeleton loading briefly
  document.getElementById('dashWaits').innerHTML = `
    <div class="skeleton skeleton-block" style="height:60px;margin-bottom:8px;"></div>
    <div class="skeleton skeleton-block" style="height:60px;margin-bottom:8px;"></div>
    <div class="skeleton skeleton-block" style="height:60px;margin-bottom:8px;"></div>
  `;
  document.getElementById('dashMap').innerHTML = `<div class="skeleton skeleton-block" style="height:300px;"></div>`;

  // GA4: track app load
  trackEvent('app_loaded', { event_category: 'system', app_name: 'VenueFlow' });

  await Promise.all([fetchAll(), checkGeminiStatus(), initGoogleMap()]);
  renderTimeline();
  drawQR();

  // Auto-refresh every 30 seconds
  setInterval(async () => {
    await fetchAll();
    const now = new Date();
    console.log(`[VenueFlow] Data refreshed at ${now.toLocaleTimeString()}`);
    trackEvent('data_refresh', { event_category: 'system', timestamp: now.toISOString() });
  }, REFRESH_INTERVAL);
})();
