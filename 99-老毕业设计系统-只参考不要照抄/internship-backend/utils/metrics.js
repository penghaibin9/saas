/**
 * 轻量指标采集（零依赖，Prometheus 文本暴露格式）
 * ───────────────────────────────────────────────────────────
 * 暴露 /metrics 供 Prometheus 抓取，补齐「出问题事后才知道」的可观测短板。
 * 采集：HTTP 请求数（按方法/状态码）、请求耗时直方图、错误数、SSE 连接数、进程指标。
 */
const counters = new Map();   // name|labels -> value
const histos = new Map();     // name -> { buckets:Map<le,count>, sum, count }
const BUCKETS = [50, 100, 200, 300, 500, 1000, 2000, 5000]; // ms

function key(name, labels) {
  if (!labels) return name;
  const l = Object.entries(labels).map(([k, v]) => `${k}="${String(v).replace(/"/g, '')}"`).join(',');
  return `${name}{${l}}`;
}

function incr(name, labels, by = 1) {
  const k = key(name, labels);
  counters.set(k, (counters.get(k) || 0) + by);
}

function observe(name, ms) {
  let h = histos.get(name);
  if (!h) { h = { buckets: new Map(BUCKETS.map((b) => [b, 0])), sum: 0, count: 0 }; histos.set(name, h); }
  h.sum += ms; h.count += 1;
  for (const b of BUCKETS) if (ms <= b) h.buckets.set(b, h.buckets.get(b) + 1);
}

// Express 中间件：记录每个请求的计数与耗时
function middleware(req, res, next) {
  const start = process.hrtime.bigint();
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - start) / 1e6;
    const route = (req.baseUrl || '') + (req.route ? req.route.path : '');
    incr('http_requests_total', { method: req.method, status: res.statusCode });
    if (res.statusCode >= 500) incr('http_errors_total', { method: req.method });
    observe('http_request_duration_ms', ms);
  });
  next();
}

function render() {
  const lines = [];
  lines.push('# HELP http_requests_total Total HTTP requests', '# TYPE http_requests_total counter');
  for (const [k, v] of counters) if (k.startsWith('http_requests_total')) lines.push(`${k} ${v}`);
  lines.push('# HELP http_errors_total Total 5xx responses', '# TYPE http_errors_total counter');
  for (const [k, v] of counters) if (k.startsWith('http_errors_total')) lines.push(`${k} ${v}`);

  for (const [name, h] of histos) {
    lines.push(`# HELP ${name} Request duration histogram (ms)`, `# TYPE ${name} histogram`);
    let cumulative = 0;
    for (const b of BUCKETS) { cumulative = h.buckets.get(b); lines.push(`${name}_bucket{le="${b}"} ${cumulative}`); }
    lines.push(`${name}_bucket{le="+Inf"} ${h.count}`);
    lines.push(`${name}_sum ${h.sum.toFixed(1)}`, `${name}_count ${h.count}`);
  }

  // SSE 在线连接
  try {
    const s = require('./sse').stats();
    lines.push('# TYPE sse_connections gauge', `sse_connections ${s.connections}`);
    lines.push('# TYPE sse_users gauge', `sse_users ${s.users}`);
  } catch (_) {}

  // 进程指标
  const mem = process.memoryUsage();
  lines.push('# TYPE process_resident_memory_bytes gauge', `process_resident_memory_bytes ${mem.rss}`);
  lines.push('# TYPE nodejs_heap_used_bytes gauge', `nodejs_heap_used_bytes ${mem.heapUsed}`);
  lines.push('# TYPE process_uptime_seconds gauge', `process_uptime_seconds ${Math.floor(process.uptime())}`);
  return lines.join('\n') + '\n';
}

module.exports = { incr, observe, middleware, render };
