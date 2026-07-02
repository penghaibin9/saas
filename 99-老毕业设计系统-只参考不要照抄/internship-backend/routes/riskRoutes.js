const express = require('express');
const { riskController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 风险预警：院校 / 分院 / 教师
router.get('/warnings', authMiddleware, requireRole(1, 2, 3), riskController.warnings);
router.post('/notify',  authMiddleware, requireRole(1, 2, 3), riskController.notifyAll);

module.exports = router;
