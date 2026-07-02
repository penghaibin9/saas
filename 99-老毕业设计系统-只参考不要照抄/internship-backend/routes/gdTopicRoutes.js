const express = require('express');
const { gdTopicController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',    authMiddleware, gdTopicController.list);
router.get('/:id', authMiddleware, gdTopicController.detail);

// 教师配备 / 选题维护：院校 & 分院管理员
router.post('/import', authMiddleware, requireRole(1, 2), gdTopicController.uploadMiddleware, gdTopicController.importExcel);
router.post('/',       authMiddleware, requireRole(1, 2), gdTopicController.create);
router.post('/:id/select',  authMiddleware, requireRole(4), gdTopicController.select);
router.put('/:id/confirm', authMiddleware, requireRole(3), gdTopicController.confirm);
router.put('/:id',     authMiddleware, requireRole(1, 2), gdTopicController.update);
router.delete('/:id',  authMiddleware, requireRole(1, 2), gdTopicController.remove);

module.exports = router;
