const express = require('express');
const { wechatController } = require('../controllers');
const { authMiddleware } = require('../middlewares/auth');
const rateLimit = require('../utils/rateLimit');

const router = express.Router();

// 微信扫码登录（公开，无需令牌）。限流防刷
const qrLimiter = rateLimit({ windowMs: 60 * 1000, max: 60, message: '操作过于频繁，请稍后再试' });

router.post('/qr',                 qrLimiter, wechatController.createQr);
router.get('/qr/:ticket',          wechatController.poll);
router.post('/qr/:ticket/confirm', qrLimiter, wechatController.confirm);

// 小程序绑定 openid（需登录）：用于后续订阅消息触达
router.post('/bind-openid', authMiddleware, wechatController.bindMpOpenid);

module.exports = router;
