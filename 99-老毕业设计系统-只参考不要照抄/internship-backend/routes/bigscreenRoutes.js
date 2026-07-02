const express = require('express');
const bigscreenController = require('../controllers/bigscreenController');

const router = express.Router();

router.get('/gis',         bigscreenController.gis);
router.get('/risk-radar',  bigscreenController.riskRadar);

module.exports = router;
