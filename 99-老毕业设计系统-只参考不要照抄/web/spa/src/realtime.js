// 站内实时推送：连接后端 SSE（/api/realtime/stream?token=），收到通知即回调。
// 用法：connectRealtime(token, (n) => toast(n.title))
let es = null;

export function connectRealtime(token, onNotification) {
  if (!token) return;
  disconnectRealtime();
  es = new EventSource('/api/realtime/stream?token=' + encodeURIComponent(token));
  es.addEventListener('notification', (e) => {
    try { onNotification && onNotification(JSON.parse(e.data)); } catch (_) {}
  });
  es.onerror = () => { /* EventSource 会自动按 retry 重连 */ };
  return es;
}

export function disconnectRealtime() {
  if (es) { es.close(); es = null; }
}
