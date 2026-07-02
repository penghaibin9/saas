const express = require('express');
const jwt = require('jsonwebtoken');
const sse = require('../utils/sse');
const { JWT_SECRET } = require('../middlewares/auth');

const router = express.Router();

/**
 * SSE 实时通道：GET /api/realtime/stream?token=<JWT>
 * EventSource 无法自定义请求头，故令牌经查询串传入并在此校验（不经标准 header 守卫）。
 * 前端：new EventSource('/api/realtime/stream?token=' + token)，监听 'notification' 事件。
 */
router.get('/stream', (req, res) => {
  const token = req.query.token;
  let user;
  try { user = jwt.verify(String(token || ''), JWT_SECRET); }
  catch { return res.status(401).json({ success: false, message: '认证令牌无效或已过期', code: 401 }); }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no', // 关闭 Nginx 缓冲，保证实时
  });
  res.write('retry: 5000\n\n');           // 断线后 5s 重连
  sse.writeEvent(res, 'ready', { ok: true });
  // 多租户：用 JWT 的 tid 显式隔离连接登记（EventSource 无法带 X-Tenant 头）
  const tid = user.tid || 'default';
  sse.addClient(user.id, res, tid);

  req.on('close', () => sse.removeClient(user.id, res, tid));
});

module.exports = router;
