const express = require('express');
const aiController = require('../controllers/aiController');
const rateLimit = require('../utils/rateLimit');

const router = express.Router();

// AI 专用限流：每客户端 1 分钟最多 20 次，缓解滥用与成本失控（AI 调用按量计费）
const aiLimiter = rateLimit({ windowMs: 60 * 1000, max: 20, message: 'AI 请求过于频繁，请稍后再试' });

router.get('/status', aiController.status);
router.get('/usage',  aiController.usage);

router.post('/score-log/:id',     aiLimiter, aiController.scoreLog);
router.post('/review-report/:id', aiLimiter, aiController.reviewReport);
router.post('/analyze-risk',      aiLimiter, aiController.analyzeRisk);
router.post('/assistant',         aiLimiter, aiController.assistant);
router.post('/match-positions',   aiLimiter, aiController.matchPositions);

module.exports = router;
