const express = require('express');
const { qualityReportController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/', authMiddleware, requireRole(1, 2), qualityReportController.generate);

module.exports = router;
