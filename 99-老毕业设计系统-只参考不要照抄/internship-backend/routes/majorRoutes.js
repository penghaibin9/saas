const express = require('express');
const { majorController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',     authMiddleware, majorController.list);
router.get('/:id',  authMiddleware, majorController.detail);

// 院校管理员 或 分院管理员 可写
router.post('/',    authMiddleware, requireRole(1, 2), majorController.create);
router.put('/:id',  authMiddleware, requireRole(1, 2), majorController.update);
router.delete('/:id', authMiddleware, requireRole(1, 2), majorController.remove);

module.exports = router;
