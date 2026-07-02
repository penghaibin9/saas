const express = require('express');
const { internStatsController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 院校/分院/教师可看实习统计
router.get('/summary',   authMiddleware, requireRole(1, 2, 3), internStatsController.summary);
router.get('/unchecked', authMiddleware, requireRole(1, 2, 3), internStatsController.uncheckedStudents);
router.get('/incomplete',authMiddleware, requireRole(1, 2, 3), internStatsController.incomplete);
router.get('/process',   authMiddleware, requireRole(1, 2, 3), internStatsController.process);

module.exports = router;
