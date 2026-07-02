const express = require('express');
const { userController } = require('../controllers');
const { authMiddleware } = require('../middlewares/auth');
const rateLimit = require('../utils/rateLimit');
const { validate } = require('../middlewares/validate');
const { authLogin, authRegister } = require('../validators/schemas');

const router = express.Router();

// 登录/注册限流：生产环境单 IP 15 分钟内最多 10 次；开发/演示环境不限流
const authLimiter = process.env.NODE_ENV === 'production'
  ? rateLimit({ windowMs: 15 * 60 * 1000, max: 10, message: '尝试过于频繁，请 15 分钟后再试' })
  : (req, res, next) => next();

router.post('/register',        authLimiter, validate(authRegister), userController.register);
router.post('/login',           authLimiter, validate(authLogin), userController.login);
router.get('/profile',          authMiddleware, userController.getProfile);
router.put('/profile',          authMiddleware, userController.updateProfile);
router.put('/change-password',  authMiddleware, userController.changePassword);

module.exports = router;
