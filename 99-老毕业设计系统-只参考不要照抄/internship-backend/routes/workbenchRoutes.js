const express = require('express');
const { workbenchController } = require('../controllers');
const { authMiddleware } = require('../middlewares/auth');

const router = express.Router();

// 我的工作台（教师/学生待办与进度聚合）
router.get('/', authMiddleware, workbenchController.index);

module.exports = router;
