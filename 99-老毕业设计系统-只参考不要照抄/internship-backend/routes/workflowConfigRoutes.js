const express = require('express');
const { workflowConfigController } = require('../controllers');
const { authMiddleware, requireRole, requirePasswordChanged } = require('../middlewares/auth');

const router = express.Router();

router.get('/', authMiddleware, requirePasswordChanged, requireRole(1, 2), workflowConfigController.list);
router.put('/steps/:id', authMiddleware, requirePasswordChanged, requireRole(1), workflowConfigController.updateStep);

module.exports = router;
