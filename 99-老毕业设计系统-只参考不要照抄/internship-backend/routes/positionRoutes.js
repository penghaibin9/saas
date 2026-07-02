const express = require('express');
const { positionController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 所有登录用户可查看岗位
router.get('/',          authMiddleware, positionController.list);
// 学生岗位智能推荐（须在 /:id 之前，避免被当作 id 匹配）
router.get('/pending',      authMiddleware, requireRole(1, 2), positionController.pending);
router.get('/recommend', authMiddleware, requireRole(4), positionController.recommend);
router.get('/:id',       authMiddleware, positionController.detail);

// 院校管理员 或 分院管理员 可管理岗位
router.post('/',               authMiddleware, requireRole(1, 2), positionController.create);
router.put('/:id/audit',       authMiddleware, requireRole(1, 2), positionController.audit);
router.put('/:id',             authMiddleware, requireRole(1, 2), positionController.update);
router.put('/:id/toggle',      authMiddleware, requireRole(1, 2), positionController.toggleStatus);
router.delete('/:id',          authMiddleware, requireRole(1, 2), positionController.remove);

module.exports = router;
