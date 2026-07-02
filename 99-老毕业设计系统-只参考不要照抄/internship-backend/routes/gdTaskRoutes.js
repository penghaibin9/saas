const express = require('express');
const { gdTaskController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查看：所有登录用户（各环节完成情况）
router.get('/',    authMiddleware, gdTaskController.list);
router.get('/:id', authMiddleware, gdTaskController.detail);

// 维护：院校 & 分院管理员
router.post('/',            authMiddleware, requireRole(1, 2), gdTaskController.create);
router.put('/:id',          authMiddleware, requireRole(1, 2), gdTaskController.update);
router.put('/:id/complete', authMiddleware, requireRole(1, 2), gdTaskController.complete);
router.delete('/:id',       authMiddleware, requireRole(1, 2), gdTaskController.remove);

module.exports = router;
