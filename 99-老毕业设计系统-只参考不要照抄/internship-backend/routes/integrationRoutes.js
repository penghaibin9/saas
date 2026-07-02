const express = require('express');
const { integrationController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/cas/redirect', integrationController.casRedirect);
router.get('/cas/callback', integrationController.casCallback);
router.post('/cas/login', integrationController.casLogin);
router.get('/info', authMiddleware, requireRole(1, 2), integrationController.info);
router.post('/webhook/test', authMiddleware, requireRole(1), integrationController.testWebhook);

module.exports = router;
