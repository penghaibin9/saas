const express = require('express');
const { reportController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',             authMiddleware, reportController.list);
router.get('/:id',          authMiddleware, reportController.detail);
router.get('/:id/download', authMiddleware, reportController.download);

// 学生操作
router.post('/',          authMiddleware, requireRole(4), reportController.upload, reportController.create);
router.put('/:id',        authMiddleware, requireRole(4), reportController.upload, reportController.update);
router.put('/:id/submit', authMiddleware, requireRole(4), reportController.submit);

// 教师评阅
router.put('/:id/review', authMiddleware, requireRole(3), reportController.review);

module.exports = router;
