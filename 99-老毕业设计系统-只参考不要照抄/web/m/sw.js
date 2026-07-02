/* 实习管理移动端 Service Worker —— 应用壳缓存 + 离线打卡队列
 * 弱网/断网场景：缓存页面壳实现离线可打开；打卡(POST /api/checkins)失败时
 * 写入 IndexedDB 队列并返回 202，联网后（sync 事件或下次请求）自动重放上报。
 */
const SHELL_CACHE = 'intern-m-shell-v2';
const SHELL_ASSETS = [
  './index.html',
  './manifest.webmanifest',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL_ASSETS).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── IndexedDB 离线队列 ──
function idb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('intern-m-db', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('checkinQueue', { keyPath: 'id', autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function queuePut(item) {
  const db = await idb();
  return new Promise((res, rej) => {
    const tx = db.transaction('checkinQueue', 'readwrite');
    tx.objectStore('checkinQueue').add(item);
    tx.oncomplete = res; tx.onerror = () => rej(tx.error);
  });
}
async function queueAll() {
  const db = await idb();
  return new Promise((res) => {
    const out = [];
    const tx = db.transaction('checkinQueue', 'readonly');
    const cur = tx.objectStore('checkinQueue').openCursor();
    cur.onsuccess = (e) => { const c = e.target.result; if (c) { out.push(c.value); c.continue(); } else res(out); };
    cur.onerror = () => res(out);
  });
}
async function queueDelete(id) {
  const db = await idb();
  return new Promise((res) => {
    const tx = db.transaction('checkinQueue', 'readwrite');
    tx.objectStore('checkinQueue').delete(id);
    tx.oncomplete = res; tx.onerror = res;
  });
}

function isCheckinPost(req) {
  return req.method === 'POST' && /\/api\/checkins(\/|\?|$)/.test(new URL(req.url).pathname);
}

async function replayQueue() {
  const items = await queueAll();
  for (const it of items) {
    try {
      const r = await fetch(it.url, { method: 'POST', headers: it.headers, body: it.body });
      if (r.ok || r.status === 409) await queueDelete(it.id); // 成功或重复(已打卡)均出队
    } catch (_) { /* 仍离线，下次再试 */ }
  }
  // 通知页面刷新离线计数
  const all = await self.clients.matchAll();
  const remain = (await queueAll()).length;
  all.forEach((c) => c.postMessage({ type: 'checkin-queue', remain }));
}

self.addEventListener('sync', (e) => { if (e.tag === 'checkin-sync') e.waitUntil(replayQueue()); });
self.addEventListener('message', (e) => { if (e.data && e.data.type === 'replay-checkin') replayQueue(); });

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 打卡 POST：在线直发；失败则入离线队列，返回 202 让前端提示"已离线缓存"
  if (isCheckinPost(req)) {
    event.respondWith((async () => {
      const headers = {};
      for (const [k, v] of req.headers.entries()) headers[k] = v;
      const body = await req.clone().text();
      try {
        return await fetch(req.clone());
      } catch (_) {
        await queuePut({ url: req.url, headers, body, at: Date.now() });
        try { if (self.registration.sync) await self.registration.sync.register('checkin-sync'); } catch (e2) {}
        return new Response(JSON.stringify({ success: true, offline: true, message: '当前网络不可用，已离线缓存，联网后自动上报' }),
          { status: 202, headers: { 'Content-Type': 'application/json' } });
      }
    })());
    return;
  }

  // 其余 API：网络优先，不缓存（保证数据实时）
  if (url.pathname.startsWith('/api/')) return;

  // 壳资源：缓存优先，回退网络
  event.respondWith(caches.match(req).then((hit) => hit || fetch(req).catch(() => caches.match('./index.html'))));
});
