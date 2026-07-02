const express = require('express');
const { insuranceController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 保险预警（需放在 /:id 之前）
router.get('/warnings', authMiddleware, requireRole(1, 2), insuranceController.warnings);
router.post('/scan',    authMiddleware, requireRole(1, 2), insuranceController.scan);

// 查看：学生看自己的；院校/分院看管理范围内的
router.get('/',    authMiddleware, requireRole(1, 2, 4), insuranceController.list);
router.get('/:id', authMiddleware, requireRole(1, 2, 4), insuranceController.detail);

// 维护：院校 & 分院管理员
router.post('/',      authMiddleware, requireRole(1, 2), insuranceController.create);
router.put('/:id',    authMiddleware, requireRole(1, 2), insuranceController.update);
router.delete('/:id', authMiddleware, requireRole(1, 2), insuranceController.remove);

module.exports = router;
