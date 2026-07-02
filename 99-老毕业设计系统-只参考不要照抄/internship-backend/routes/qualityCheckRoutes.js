const express = require('express');
const { qualityCheckController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',    authMiddleware, qualityCheckController.list);
router.get('/:id', authMiddleware, qualityCheckController.detail);

// 互查布置：院校 & 分院管理员
router.post('/generate', authMiddleware, requireRole(1, 2), qualityCheckController.generate);
router.post('/',         authMiddleware, requireRole(1, 2), qualityCheckController.create);
router.delete('/:id',    authMiddleware, requireRole(1, 2), qualityCheckController.remove);

// 自查/互查审阅：教师
router.put('/:id/review', authMiddleware, requireRole(3), qualityCheckController.review);

module.exports = router;
