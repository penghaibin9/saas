const express = require('express');
const workflowController = require('../controllers/workflowController');
const { validate } = require('../middlewares/validate');
const { wfDispatch, wfDefinition } = require('../validators/schemas');

const router = express.Router();

// 管理端：流程定义配置（须在 /:bizType 动态路由之前注册）
router.get('/defs', workflowController.listDefs);
router.get('/def/:bizType', workflowController.getDef);
router.put('/def/:bizType', validate(wfDefinition), workflowController.setDefinition);
router.put('/def/:bizType/enabled', workflowController.setEnabled);
router.post('/seed', workflowController.seed);

// 业务端：查看状态 / 驱动流转
router.get('/:bizType/:bizId', workflowController.current);
router.post('/:bizType/:bizId/dispatch', validate(wfDispatch), workflowController.dispatch);

module.exports = router;
