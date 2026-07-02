const express = require('express');
const { systemConfigController } = require('../controllers');
const { authMiddleware, requireRole, requirePasswordChanged } = require('../middlewares/auth');

const router = express.Router();

router.get('/public', systemConfigController.getPublic);
router.get('/channels', authMiddleware, requirePasswordChanged, requireRole(1, 2), systemConfigController.getChannels);
router.get('/', authMiddleware, requirePasswordChanged, requireRole(1, 2), systemConfigController.getAll);
router.put('/', authMiddleware, requirePasswordChanged, requireRole(1), systemConfigController.update);

module.exports = router;
