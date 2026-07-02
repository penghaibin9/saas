const express = require('express');
const { gdGuidanceController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',    authMiddleware, gdGuidanceController.list);
router.get('/:id', authMiddleware, gdGuidanceController.detail);

// 教师维护指导记录
router.post('/',      authMiddleware, requireRole(3), gdGuidanceController.create);
router.put('/:id',    authMiddleware, requireRole(3), gdGuidanceController.update);
router.delete('/:id', authMiddleware, requireRole(3), gdGuidanceController.remove);

module.exports = router;
