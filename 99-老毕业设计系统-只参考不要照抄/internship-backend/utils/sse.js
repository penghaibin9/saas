/**
 * 站内实时推送（SSE，Server-Sent Events）+ 跨实例广播（Redis Pub/Sub）
 * ───────────────────────────────────────────────────────────
 * 把新通知/待办实时推到前端，替代纯轮询。零依赖、基于原生 HTTP。
 *
 * 多租户隔离：连接按「租户#用户」复合键登记，避免不同学校的同号用户串推。
 *
 * 多实例广播（V2）：
 *   · 默认（无 REDIS_URL）：单进程内存推送——同一用户连到哪个实例就由哪个实例推。
 *   · 配置 REDIS_URL 且装了 ioredis：经 Redis 频道 `sse:push` 广播，
 *     每个实例订阅后推给本地连接。用户连到 A 实例、事件在 B 实例产生，也能送达。
 *     发布端只发布不本地直推（由各实例订阅回调统一本地推），保证「单次送达、不重复」。
 *   Redis 异常时回退本地直推（fail-open，不因缓存故障丢实时、更不拖垮业务）。
 */
const tenancy = require('../config/tenancy');

const clients = new Map(); // `${tenantCode}#${userId}` -> Set<res>
const CHANNEL = 'sse:push';

function keyOf(tenantCode, userId) {
  return `${tenantCode || 'default'}#${Number(userId)}`;
}

/** 当前请求所属租户 code（脚本/单租户兜底 default） */
function currentTenantCode() {
  try { const t = tenancy.currentTenant(); return (t && t.code) || tenancy.DEFAULT_TENANT_CODE; }
  catch { return 'default'; }
}

// ── Redis Pub/Sub（懒加载，缺省关闭）────────────────────────────
let _pub = null;       // 发布连接
let _subReady = false;  // 订阅是否已建立
let _redisTried = false;
let _redisOn = false;

function initRedis() {
  if (_redisTried) return _redisOn;
  _redisTried = true;
  if (!process.env.REDIS_URL) return false;
  try {
    const Redis = require('ioredis');
    _pub = new Redis(process.env.REDIS_URL, { maxRetriesPerRequest: 2 });
    _pub.on('error', (e) => console.warn('⚠️  Redis(SSE 发布)异常（将回退本地推送）:', e.message));
    const sub = new Redis(process.env.REDIS_URL, { maxRetriesPerRequest: 2 });
    sub.on('error', (e) => console.warn('⚠️  Redis(SSE 订阅)异常:', e.message));
    sub.subscribe(CHANNEL, (err) => {
      if (err) { console.warn('⚠️  Redis(SSE)订阅失败，回退本地推送:', err.message); return; }
      _subReady = true;
      console.log('📡 SSE 后端：Redis Pub/Sub（多实例广播）');
    });
    sub.on('message', (_ch, payload) => {
      try {
        const m = JSON.parse(payload);
        localPush(m.tenantCode, m.userId, m.event, m.data);
      } catch (_) { /* 坏消息忽略 */ }
    });
    _redisOn = true;
  } catch (e) {
    console.warn('⚠️  未安装 ioredis，SSE 回退单进程本地推送：', e.message);
    _redisOn = false;
  }
  return _redisOn;
}

function addClient(userId, res, tenantCode) {
  initRedis();
  const k = keyOf(tenantCode != null ? tenantCode : currentTenantCode(), userId);
  if (!clients.has(k)) clients.set(k, new Set());
  clients.get(k).add(res);
}

function removeClient(userId, res, tenantCode) {
  const k = keyOf(tenantCode != null ? tenantCode : currentTenantCode(), userId);
  const set = clients.get(k);
  if (!set) return;
  set.delete(res);
  if (!set.size) clients.delete(k);
}

function writeEvent(res, event, data) {
  try {
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  } catch (_) { /* 连接已断，由 close 清理 */ }
}

/** 仅推送给本实例上该「租户#用户」的在线连接 */
function localPush(tenantCode, userId, event, data) {
  const set = clients.get(keyOf(tenantCode, userId));
  if (!set || !set.size) return 0;
  for (const res of set) writeEvent(res, event, data);
  return set.size;
}

/**
 * 向某用户推送一条事件（自动按当前租户隔离 + 多实例广播）。
 * Redis 开启：发布到频道（各实例订阅回调统一本地推，单次送达）；
 * 未开启/异常：本实例直接本地推。
 */
function pushToUser(userId, event, data, tenantCode) {
  const tc = tenantCode != null ? tenantCode : currentTenantCode();
  if (initRedis() && _pub && _subReady) {
    try {
      _pub.publish(CHANNEL, JSON.stringify({ tenantCode: tc, userId: Number(userId), event, data }));
      return; // 由订阅回调本地推，避免重复
    } catch (e) {
      console.warn('SSE(Redis 发布)异常，回退本地推送:', e.message);
    }
  }
  return localPush(tc, userId, event, data);
}

/** 当前在线连接数（监控用） */
function stats() {
  let conns = 0;
  for (const set of clients.values()) conns += set.size;
  return { keys: clients.size, connections: conns, redis: _redisOn && _subReady };
}

// 心跳：每 25s 发送注释行保活，防代理/网关断开空闲连接
const heartbeat = setInterval(() => {
  for (const set of clients.values()) for (const res of set) {
    try { res.write(': ping\n\n'); } catch (_) {}
  }
}, 25000);
if (typeof heartbeat.unref === 'function') heartbeat.unref();

module.exports = { addClient, removeClient, pushToUser, writeEvent, stats, keyOf, currentTenantCode };
