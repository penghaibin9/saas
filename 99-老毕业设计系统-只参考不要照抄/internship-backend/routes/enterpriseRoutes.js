const express = require('express');
const { enterpriseController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 待审核入驻企业（需放在 /:id 之前，避免被动态路由吞掉）
router.get('/pending', authMiddleware, requireRole(1, 2), enterpriseController.pending);

// 所有登录用户可查
router.get('/',     authMiddleware, enterpriseController.list);
router.get('/:id',  authMiddleware, enterpriseController.detail);

// 院校管理员 或 分院管理员 可写
router.post('/',         authMiddleware, requireRole(1, 2), enterpriseController.create);
router.put('/:id/audit', authMiddleware, requireRole(1, 2), enterpriseController.audit);
router.put('/:id',       authMiddleware, requireRole(1, 2), enterpriseController.update);
router.delete('/:id',    authMiddleware, requireRole(1, 2), enterpriseController.remove);

module.exports = router;
