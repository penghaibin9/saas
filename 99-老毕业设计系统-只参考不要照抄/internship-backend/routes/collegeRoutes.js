const express = require('express');
const { collegeController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 所有人登录后可查
router.get('/',    authMiddleware, collegeController.list);
router.get('/:id', authMiddleware, collegeController.detail);

// 仅院校管理员可写
router.post('/',    authMiddleware, requireRole(1), collegeController.create);
router.put('/:id',  authMiddleware, requireRole(1), collegeController.update);
router.delete('/:id', authMiddleware, requireRole(1), collegeController.remove);

module.exports = router;
