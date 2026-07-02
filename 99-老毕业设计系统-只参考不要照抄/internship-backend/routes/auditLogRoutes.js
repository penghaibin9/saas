const express = require('express');
const { auditLogController } = require('../controllers');
const { requireRole } = require('../middlewares/auth');

const router = express.Router();

// 仅院校管理员(1)与分院管理员(2)可查看审计日志
router.get('/',         requireRole(1, 2), auditLogController.list);
router.get('/overview', requireRole(1, 2), auditLogController.overview);

module.exports = router;
