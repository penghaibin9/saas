const express = require('express');
const { leaveController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',    authMiddleware, leaveController.list);
router.get('/:id', authMiddleware, leaveController.detail);

// 学生：创建/修改/提交/删除
router.post('/',          authMiddleware, requireRole(4), leaveController.create);
router.put('/:id',        authMiddleware, requireRole(4), leaveController.update);
router.put('/:id/submit', authMiddleware, requireRole(4), leaveController.submit);
router.delete('/:id',     authMiddleware, requireRole(4), leaveController.remove);

// 教师：审批
router.put('/:id/review', authMiddleware, requireRole(3), leaveController.review);

module.exports = router;
