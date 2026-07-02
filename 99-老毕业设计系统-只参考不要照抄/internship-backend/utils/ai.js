/**
 * AI 能力服务层（基于 DeepSeek，可插拔 + 降级演示）
 * ───────────────────────────────────────────────────────────
 * 设计目标：与 utils/plagiarism.js、utils/sms.js 一致的"配置即真用、未配置即演示"范式：
 *   · 配置了 DEEPSEEK_API_KEY → 调用 DeepSeek（OpenAI 兼容接口）做真实智能分析；
 *   · 未配置（含私有化无外网环境）→ 返回带 isDemo=1 标记的确定性启发式结果，
 *     绝不伪装成模型输出，也不阻断主业务。
 *
 * 采用原生 fetch（零依赖，与 utils/plagiarism.js 一致），无需安装任何 SDK；
 * DeepSeek 为 OpenAI 兼容 API，POST /chat/completions，可直接切换自建网关/代理。
 *
 * 环境变量：
 *   DEEPSEEK_API_KEY    DeepSeek API 密钥（缺省即演示模式）
 *   DEEPSEEK_MODEL      模型 ID，默认 deepseek-chat（深度推理可用 deepseek-reasoner）
 *   DEEPSEEK_BASE_URL   接口基址，默认 https://api.deepseek.com
 *   AI_TIMEOUT_MS       单次调用超时，默认 60000
 */

const { scrubText } = require('./desensitize');
const aiUsage = require('../models/aiUsageModel');

const MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-chat';
const BASE_URL = (process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com').replace(/\/$/, '');
const TIMEOUT_MS = Number(process.env.AI_TIMEOUT_MS || 60000);
const MONTHLY_QUOTA = Number(process.env.AI_MONTHLY_QUOTA || 0); // 0=不限

function isConfigured() {
  return !!process.env.DEEPSEEK_API_KEY;
}

// 配额校验：超出当月上限时抛出，触发演示降级（防账单失控）
async function ensureQuota() {
  if (MONTHLY_QUOTA <= 0) return;
  const used = await aiUsage.monthTotal();
  if (used >= MONTHLY_QUOTA) throw new Error('AI_QUOTA_EXCEEDED');
}

/**
 * 调用 DeepSeek 并要求返回 JSON。失败时抛错，由上层决定是否降级。
 * @returns {Promise<object>} 解析后的 JSON
 */
async function callJSON(system, userPrompt, { maxTokens = 1024 } = {}) {
  if (!isConfigured()) throw new Error('AI 未配置');
  await ensureQuota();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + process.env.DEEPSEEK_API_KEY,
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: maxTokens,
        temperature: 0.3,
        // DeepSeek/OpenAI 兼容的 JSON 输出模式（提示词中需含 "json" 字样）
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: system + '\n\n请只输出一个 JSON 对象（json 格式），不要包含解释文字或代码块标记。' },
          // 数据最小化：发送前掩码用户文本中夹带的手机号/身份证/邮箱，避免 PII 外发第三方
          { role: 'user', content: scrubText(userPrompt) },
        ],
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error('DeepSeek 返回 HTTP ' + res.status);
    const data = await res.json();
    const text = data && data.choices && data.choices[0] && data.choices[0].message
      ? String(data.choices[0].message.content || '')
      : '';
    const parsed = parseJSONLoose(text);
    aiUsage.incr(1).catch(() => {}); // 计量当月成功调用（不阻断）
    return parsed;
  } finally {
    clearTimeout(timer);
  }
}

// 容错解析：去除可能的 ```json 包裹/前后缀，抽取首个 JSON 对象
function parseJSONLoose(text) {
  if (!text) throw new Error('AI 返回为空');
  let s = String(text).replace(/^```(?:json)?/i, '').replace(/```$/i, '').trim();
  const start = s.indexOf('{');
  const end = s.lastIndexOf('}');
  if (start >= 0 && end > start) s = s.slice(start, end + 1);
  return JSON.parse(s);
}

function clamp(n, lo, hi, dflt) {
  const v = Number(n);
  if (!Number.isFinite(v)) return dflt;
  return Math.max(lo, Math.min(hi, v));
}

// ── 演示降级：确定性启发式（基于文本特征，明确 isDemo） ──
const STOP_HINTS = ['今天', '今日', '继续', '正常', '一切顺利', '没什么', '同上', '略', '无'];
const RISK_WORDS = ['离职', '辞职', '不想干', '受伤', '工伤', '事故', '危险', '加班到', '通宵',
  '克扣', '欠薪', '没发工资', '压力大', '抑郁', '想不开', '骂', '打人', '脱岗', '旷工', '投诉'];

function demoScoreLog({ content = '' } = {}) {
  const text = String(content);
  const len = text.replace(/\s/g, '').length;
  const lines = text.split(/\n/).filter((l) => l.trim()).length;
  const lazy = STOP_HINTS.some((w) => text.includes(w)) && len < 40;
  let score = 60;
  if (len >= 120) score += 15; else if (len < 30) score -= 25;
  if (lines >= 3) score += 10;
  if (lazy) score -= 20;
  score = clamp(score, 5, 95, 60);
  const suggestions = [];
  if (len < 60) suggestions.push('内容偏少，建议补充具体工作任务、遇到的问题与解决过程');
  if (lines < 2) suggestions.push('建议按"内容/收获/问题/计划"分点撰写，条理更清晰');
  if (lazy) suggestions.push('表述较为笼统，建议写明可量化的成果或数据');
  if (!suggestions.length) suggestions.push('结构与篇幅良好，可进一步提炼亮点与反思');
  return {
    score, dimensions: { 充实度: clamp(len / 2, 5, 100, 50), 条理性: clamp(lines * 20, 5, 100, 40), 反思深度: lazy ? 30 : 65 },
    summary: lazy ? '内容较为敷衍，建议充实具体细节' : '内容基本完整',
    suggestions, isDemo: true,
  };
}

function demoReviewReport({ content = '' } = {}) {
  const d = demoScoreLog({ content });
  return {
    score: d.score,
    comment: '（演示）报告' + (d.score >= 75 ? '结构完整、内容充实，达到实习报告要求。' : '内容有待充实，建议补充实践细节与个人反思。'),
    strengths: d.score >= 75 ? ['篇幅充足', '条理较清晰'] : ['已涵盖基本要素'],
    improvements: d.suggestions,
    isDemo: true,
  };
}

function demoAnalyzeRisk({ text = '' } = {}) {
  const s = String(text);
  const hits = RISK_WORDS.filter((w) => s.includes(w));
  let level = 'none';
  if (hits.length >= 2) level = 'high';
  else if (hits.length === 1) level = 'medium';
  return {
    level,
    signals: hits,
    advice: level === 'none' ? '未发现明显风险信号' : '检测到潜在风险关键词，建议指导教师及时关注并联系学生核实',
    isDemo: true,
  };
}

function demoAssistant({ question = '' } = {}) {
  return {
    answer: '（演示模式）系统未配置 AI 服务，无法生成智能回答。常见实习政策与流程请查阅"系统使用说明"或咨询实训中心。问题：' + String(question).slice(0, 80),
    isDemo: true,
  };
}

function demoMatch({ skills = '', positions = [] } = {}) {
  const kw = String(skills).split(/[,，、\s]+/).filter(Boolean);
  const ranked = positions.map((p) => {
    const hay = `${p.title || ''} ${p.requirement || ''} ${p.description || ''}`;
    const hitCount = kw.filter((k) => hay.includes(k)).length;
    const score = clamp(40 + hitCount * 15, 10, 95, 50);
    return { positionId: p.id, title: p.title, score, reason: hitCount ? `匹配技能关键词 ${hitCount} 项` : '基础匹配' };
  }).sort((a, b) => b.score - a.score);
  return { ranked, isDemo: true };
}

// ── 对外能力（真用优先，失败/未配置自动降级，且如实标记 isDemo） ──

async function scoreLog(input) {
  if (!isConfigured()) return demoScoreLog(input);
  try {
    const out = await callJSON(
      '你是职业院校实习管理系统的教学助手，请客观评估学生实习周报/月报的质量。',
      `请评估以下实习${input.type === 'monthly' ? '月报' : '周报'}并返回 JSON：{"score":0-100整数,"dimensions":{"充实度":0-100,"条理性":0-100,"反思深度":0-100},"summary":"一句话总评","suggestions":["改进建议","..."]}。\n\n标题：${input.title || ''}\n正文：\n${input.content || ''}`,
      { maxTokens: 1024 }
    );
    return {
      score: clamp(out.score, 0, 100, 60),
      dimensions: out.dimensions || {},
      summary: String(out.summary || '').slice(0, 200),
      suggestions: Array.isArray(out.suggestions) ? out.suggestions.slice(0, 6) : [],
      isDemo: false,
    };
  } catch (e) {
    console.warn('AI 日志质检失败，降级演示：', e.message);
    return demoScoreLog(input);
  }
}

async function reviewReport(input) {
  if (!isConfigured()) return demoReviewReport(input);
  try {
    const out = await callJSON(
      '你是职业院校指导教师的智能助手，请辅助评阅学生实习报告，给出客观、建设性的评语初稿，最终以教师确认为准。',
      `请评阅以下实习报告并返回 JSON：{"score":0-100整数,"comment":"评语初稿","strengths":["优点"],"improvements":["改进建议"]}。\n\n标题：${input.title || ''}\n正文：\n${(input.content || '').slice(0, 8000)}`,
      { maxTokens: 1536 }
    );
    return {
      score: clamp(out.score, 0, 100, 70),
      comment: String(out.comment || '').slice(0, 1000),
      strengths: Array.isArray(out.strengths) ? out.strengths.slice(0, 6) : [],
      improvements: Array.isArray(out.improvements) ? out.improvements.slice(0, 6) : [],
      isDemo: false,
    };
  } catch (e) {
    console.warn('AI 报告评阅失败，降级演示：', e.message);
    return demoReviewReport(input);
  }
}

async function analyzeRiskText(input) {
  if (!isConfigured()) return demoAnalyzeRisk(input);
  try {
    const out = await callJSON(
      '你是实习安全监管助手，请从学生提交的文本中识别安全/权益/心理等潜在风险信号，宁可多报不可漏报，但不得编造。',
      `请分析以下文本是否包含风险信号，返回 JSON：{"level":"none|low|medium|high","signals":["命中的风险点"],"advice":"给指导教师的处置建议"}。\n\n文本：\n${(input.text || '').slice(0, 4000)}`,
      { maxTokens: 768 }
    );
    const level = ['none', 'low', 'medium', 'high'].includes(out.level) ? out.level : 'none';
    return {
      level,
      signals: Array.isArray(out.signals) ? out.signals.slice(0, 10) : [],
      advice: String(out.advice || '').slice(0, 500),
      isDemo: false,
    };
  } catch (e) {
    console.warn('AI 风险分析失败，降级演示：', e.message);
    return demoAnalyzeRisk(input);
  }
}

async function assistantAnswer(input) {
  if (!isConfigured()) return demoAssistant(input);
  try {
    const out = await callJSON(
      `你是职业院校实习管理平台的智能助手，面向${input.role || '用户'}解答实习/毕设相关政策与流程问题，回答要准确、简洁、可执行；不确定时如实说明并建议咨询实训中心，不得编造制度条款。`,
      `用户问题：${String(input.question || '').slice(0, 1000)}\n请返回 JSON：{"answer":"回答正文"}`,
      { maxTokens: 1024 }
    );
    return { answer: String(out.answer || '').slice(0, 2000), isDemo: false };
  } catch (e) {
    console.warn('AI 助手回答失败，降级演示：', e.message);
    return demoAssistant(input);
  }
}

async function matchPositions(input) {
  if (!isConfigured()) return demoMatch(input);
  try {
    const list = (input.positions || []).slice(0, 30).map((p) => ({
      id: p.id, title: p.title, requirement: (p.requirement || '').slice(0, 300),
    }));
    const out = await callJSON(
      '你是实习岗位智能推荐助手，请根据学生技能为其匹配最合适的岗位并排序。',
      `学生技能：${input.skills || ''}\n候选岗位（JSON）：${JSON.stringify(list)}\n请返回 JSON：{"ranked":[{"positionId":岗位id,"score":0-100,"reason":"匹配理由"}]}（按 score 降序）`,
      { maxTokens: 1536 }
    );
    const byId = new Map(list.map((p) => [p.id, p.title]));
    const ranked = (Array.isArray(out.ranked) ? out.ranked : []).map((r) => ({
      positionId: r.positionId,
      title: byId.get(r.positionId) || '',
      score: clamp(r.score, 0, 100, 50),
      reason: String(r.reason || '').slice(0, 200),
    }));
    return { ranked, isDemo: false };
  } catch (e) {
    console.warn('AI 岗位匹配失败，降级演示：', e.message);
    return demoMatch(input);
  }
}

function status() {
  return { configured: isConfigured(), model: isConfigured() ? MODEL : '', mode: isConfigured() ? 'live' : 'demo' };
}

// 当月用量与配额（管理员查看）
async function usageStatus() {
  const used = await aiUsage.monthTotal();
  return {
    period: aiUsage.curMonth(),
    calls: used,
    quota: MONTHLY_QUOTA || null,
    remaining: MONTHLY_QUOTA ? Math.max(0, MONTHLY_QUOTA - used) : null,
    exceeded: MONTHLY_QUOTA ? used >= MONTHLY_QUOTA : false,
  };
}

module.exports = {
  isConfigured, status, usageStatus,
  scoreLog, reviewReport, analyzeRiskText, assistantAnswer, matchPositions,
};
