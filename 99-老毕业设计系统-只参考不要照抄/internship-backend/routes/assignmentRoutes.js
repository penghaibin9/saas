const express = require('express');
const { assignmentController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',    authMiddleware, assignmentController.list);
router.get('/:id', authMiddleware, assignmentController.detail);

// 院校 & 分院管理员：分配、修改、移除、导入
router.get('/import/template', authMiddleware, requireRole(1, 2), assignmentController.downloadTemplate);
router.post('/import',         authMiddleware, requireRole(1, 2), assignmentController.uploadMiddleware, assignmentController.importExcel);
router.post('/',               authMiddleware, requireRole(1, 2), assignmentController.create);
router.put('/:id',             authMiddleware, requireRole(1, 2), assignmentController.update);
router.delete('/:id',          authMiddleware, requireRole(1, 2), assignmentController.remove);

module.exports = router;
