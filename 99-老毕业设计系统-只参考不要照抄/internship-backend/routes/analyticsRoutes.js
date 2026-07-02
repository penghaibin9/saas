const express = require('express');
const { analyticsController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 可视化分析：仅院校 & 分院管理员
router.get('/cockpit',    authMiddleware, requireRole(1, 2), analyticsController.cockpit);
router.get('/intern',     authMiddleware, requireRole(1, 2), analyticsController.intern);
router.get('/gd',         authMiddleware, requireRole(1, 2), analyticsController.gd);
router.get('/gd-summary', authMiddleware, requireRole(1, 2), analyticsController.gdSummary);
router.get('/excellence', authMiddleware, requireRole(1, 2), analyticsController.excellence);

module.exports = router;
