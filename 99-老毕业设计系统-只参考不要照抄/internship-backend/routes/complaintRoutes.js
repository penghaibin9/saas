const express = require('express');
const { complaintController } = require('../controllers');
const { requireRole } = require('../middlewares/auth');

// 挂载处已过 authMiddleware + requirePasswordChanged
const router = express.Router();

router.get('/',           complaintController.list);          // 各角色按范围查看
router.get('/overview',   complaintController.overview);
router.post('/',          complaintController.create);        // 任意登录用户可上报
router.get('/:id',        complaintController.detail);
router.put('/:id/handle', requireRole(1, 2, 3), complaintController.handle); // 管理员/教师处理

module.exports = router;
