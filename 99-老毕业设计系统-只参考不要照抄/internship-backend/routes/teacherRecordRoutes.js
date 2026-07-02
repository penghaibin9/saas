const express = require('express');
const { teacherRecordController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查看：教师看自己 / 分院看本院 / 院校看全部
router.get('/',    authMiddleware, requireRole(1, 2, 3), teacherRecordController.list);
router.get('/:id', authMiddleware, requireRole(1, 2, 3), teacherRecordController.detail);

// 教师维护（月报/寻访，草稿/提交，支持附件）
router.post('/',          authMiddleware, requireRole(3), teacherRecordController.upload, teacherRecordController.create);
router.put('/:id',        authMiddleware, requireRole(3), teacherRecordController.upload, teacherRecordController.update);
router.put('/:id/submit', authMiddleware, requireRole(3), teacherRecordController.submit);
router.delete('/:id',     authMiddleware, requireRole(3), teacherRecordController.remove);

module.exports = router;
