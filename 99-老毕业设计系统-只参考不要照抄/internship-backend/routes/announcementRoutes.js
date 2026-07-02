const express = require('express');
const { announcementController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查看：所有登录用户（按角色/可见性过滤）
router.get('/',    authMiddleware, announcementController.list);
router.get('/:id', authMiddleware, announcementController.detail);

// 维护：院校 & 分院管理员（支持附件）
router.post('/',      authMiddleware, requireRole(1, 2), announcementController.upload, announcementController.create);
router.put('/:id',    authMiddleware, requireRole(1, 2), announcementController.upload, announcementController.update);
router.delete('/:id', authMiddleware, requireRole(1, 2), announcementController.remove);

module.exports = router;
