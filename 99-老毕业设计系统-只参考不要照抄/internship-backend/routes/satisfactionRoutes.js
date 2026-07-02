const express = require('express');
const { satisfactionController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 分析（院校/分院）放在动态路由之前
router.get('/analytics', authMiddleware, requireRole(1, 2), satisfactionController.analytics);

// 查看 & 维护：院校/分院/教师可填写评价
router.get('/',       authMiddleware, requireRole(1, 2, 3), satisfactionController.list);
router.post('/',      authMiddleware, requireRole(1, 2, 3), satisfactionController.create);
router.delete('/:id', authMiddleware, requireRole(1, 2),    satisfactionController.remove);

module.exports = router;
