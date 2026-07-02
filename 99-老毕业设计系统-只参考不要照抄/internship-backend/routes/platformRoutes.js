const express = require('express');
const platformController = require('../controllers/platformController');
const { validate } = require('../middlewares/validate');
const { platformProvision } = require('../validators/schemas');

// 平台运营控制台（跨租户，不经租户路由）。挂载点在 app.js 以 requirePlatformAdmin 守卫。
const router = express.Router();

router.get('/tenants',                 platformController.listTenants);
router.post('/tenants',                validate(platformProvision), platformController.provision);
router.get('/tenants/:code',           platformController.getTenant);
router.put('/tenants/:code/plan',      platformController.setPlan);
router.put('/tenants/:code/quota',     platformController.setQuota);
router.put('/tenants/:code/renew',     platformController.renew);
router.post('/tenants/:code/suspend',  platformController.suspend);
router.post('/tenants/:code/resume',   platformController.resume);
router.post('/tenants/:code/refresh-usage', platformController.refreshUsage);
router.get('/plans',                   platformController.plans);
router.get('/pool-stats',              platformController.poolStats);
// V2：计费对账 + 监管局跨校驾驶舱
router.get('/billing',                 platformController.billing);
router.post('/billing/refresh',        platformController.billingRefresh);
router.get('/supervision',             platformController.supervision);

module.exports = router;
