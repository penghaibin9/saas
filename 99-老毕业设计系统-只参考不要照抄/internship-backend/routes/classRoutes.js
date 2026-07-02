const express = require('express');
const { classController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',     authMiddleware, classController.list);
router.get('/:id',  authMiddleware, classController.detail);

// 院校管理员 或 分院管理员 可写
router.post('/',      authMiddleware, requireRole(1, 2), classController.create);
router.put('/:id',    authMiddleware, requireRole(1, 2), classController.update);
router.delete('/:id', authMiddleware, requireRole(1, 2), classController.remove);

module.exports = router;
