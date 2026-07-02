const express = require('express');
const { adminUserController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 院校管理员 和 分院管理员 可管理用户
router.get('/',                  authMiddleware, requireRole(1, 2), adminUserController.list);
router.get('/:id',               authMiddleware, requireRole(1, 2), adminUserController.detail);
router.post('/',                 authMiddleware, requireRole(1, 2), adminUserController.create);
router.put('/:id',               authMiddleware, requireRole(1, 2), adminUserController.update);
router.put('/:id/reset-password',authMiddleware, requireRole(1, 2), adminUserController.resetPassword);
router.put('/:id/toggle-status', authMiddleware, requireRole(1, 2), adminUserController.toggleStatus);
router.delete('/:id',            authMiddleware, requireRole(1),    adminUserController.remove);

module.exports = router;
