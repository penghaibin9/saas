const express = require('express');
const { notificationController } = require('../controllers');
const { authMiddleware } = require('../middlewares/auth');

const router = express.Router();

router.get('/',              authMiddleware, notificationController.list);
router.get('/unread-count',  authMiddleware, notificationController.unreadCount);
router.put('/:id/read',      authMiddleware, notificationController.markRead);
router.put('/read-all',      authMiddleware, notificationController.markAllRead);

module.exports = router;
