const express = require('express');
const { gdGradeController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 学生查看本人成绩
router.get('/mine', authMiddleware, requireRole(4), gdGradeController.mine);

// 列表：院校/分院/教师
router.get('/', authMiddleware, requireRole(1, 2, 3), gdGradeController.list);

// 录入/导入：教师（院校/分院也可）
router.post('/import', authMiddleware, requireRole(1, 2, 3), gdGradeController.uploadMiddleware, gdGradeController.importExcel);
router.post('/',       authMiddleware, requireRole(1, 2, 3), gdGradeController.upsert);
router.delete('/:id',  authMiddleware, requireRole(1, 2), gdGradeController.remove);

module.exports = router;
