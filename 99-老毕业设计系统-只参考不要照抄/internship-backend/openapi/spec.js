/**
 * OpenAPI 3.0 接口契约（招投标/对接交付）
 * ───────────────────────────────────────────────────────────
 * curated 规范：覆盖认证、核心资源、SaaS 平台运营等主干接口，字段契约与
 * validators/schemas.js（zod 运行期校验）一致。服务于 /api/openapi.json + /api/docs。
 * 全量 200+ 接口可在此持续补充，或后续接入自动生成。
 */
const ok = (dataSchema) => ({
  type: 'object',
  properties: { success: { type: 'boolean', example: true }, message: { type: 'string' }, data: dataSchema || {} },
});
const errSchema = { type: 'object', properties: { success: { type: 'boolean', example: false }, code: { type: 'string' }, message: { type: 'string' } } };
const jsonBody = (schema) => ({ required: true, content: { 'application/json': { schema } } });
const jsonResp = (desc, schema) => ({ description: desc, content: { 'application/json': { schema } } });
const errResp = (desc) => ({ description: desc, content: { 'application/json': { schema: errSchema } } });

function buildSpec(baseUrl) {
  return {
    openapi: '3.0.3',
    info: {
      title: '岗位实习与毕业设计管理平台 API',
      version: '1.0.0',
      description: '职业院校实习+毕业设计管理 SaaS。多租户(DB-per-tenant)、RBAC+数据范围、AI 风险预警。\n\n- 业务接口前缀：`/api/v1`（旧 `/api` 过渡可用，带弃用头）\n- 认证：除登录/公开接口外，均需 `Authorization: Bearer <JWT>`\n- 平台运营接口 `/api/platform/*` 用 `PLATFORM_ADMIN_TOKEN`',
    },
    servers: [{ url: (baseUrl || '') + '/api/v1', description: '业务 API v1' }, { url: (baseUrl || ''), description: '根（含 /api/platform）' }],
    tags: [
      { name: '认证', description: '登录/注册/改密' },
      { name: '用户', description: '用户与角色' },
      { name: '实习报酬', description: '报酬台账与合规' },
      { name: 'AI', description: 'AI 智能能力' },
      { name: '监管大屏', description: 'GIS/风险雷达' },
      { name: '流程引擎', description: '配置化审批流转' },
      { name: '产品概览', description: '学校采购演示与校级聚合统计' },
      { name: '平台运营(SaaS)', description: '租户/套餐/配额/开通' },
      { name: '系统', description: '健康检查/指标' },
    ],
    components: {
      securitySchemes: {
        bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT', description: '登录获取的用户 JWT' },
        platformAuth: { type: 'http', scheme: 'bearer', description: '平台运营令牌 PLATFORM_ADMIN_TOKEN' },
      },
      schemas: {
        LoginReq: { type: 'object', required: ['username', 'password'], properties: { username: { type: 'string' }, password: { type: 'string', format: 'password' } } },
        RegisterReq: { type: 'object', required: ['username', 'password', 'real_name'], properties: { username: { type: 'string', minLength: 3 }, password: { type: 'string', minLength: 6 }, real_name: { type: 'string' }, phone: { type: 'string' }, email: { type: 'string', format: 'email' } } },
        StipendCreateReq: { type: 'object', required: ['student_id', 'period'], properties: { student_id: { type: 'integer' }, period: { type: 'string', example: '2026-06', pattern: '^\\d{4}-(0[1-9]|1[0-2])$' }, amount: { type: 'number' }, base_salary_ref: { type: 'number' }, method: { type: 'string', enum: ['bank', 'cash', 'wechat', 'alipay'] } } },
        ProvisionReq: { type: 'object', required: ['code', 'name'], properties: { code: { type: 'string', example: 'hnsh' }, name: { type: 'string' }, plan: { type: 'string', enum: ['trial', 'standard', 'pro'] }, expire_date: { type: 'string', format: 'date' }, region: { type: 'string' }, contact_name: { type: 'string' }, contact_phone: { type: 'string' } } },
        WfDispatchReq: { type: 'object', required: ['action'], properties: { action: { type: 'string', example: 'approve' }, remark: { type: 'string' } } },
        // ── 实体（供前端类型生成）──
        User: { type: 'object', properties: { id: { type: 'integer' }, username: { type: 'string' }, realName: { type: 'string' }, role: { type: 'integer' }, roleName: { type: 'string' }, collegeId: { type: 'integer' }, eeid: { type: 'string' }, status: { type: 'integer' } } },
        Plan: { type: 'object', properties: { code: { type: 'string' }, name: { type: 'string' }, price_year: { type: 'number' }, max_students: { type: 'integer' }, max_storage_mb: { type: 'integer' }, ai_monthly_quota: { type: 'integer' } } },
        Tenant: { type: 'object', properties: { code: { type: 'string' }, name: { type: 'string' }, db_name: { type: 'string' }, plan: { type: 'string' }, expire_date: { type: 'string', format: 'date' }, status: { type: 'integer' }, max_students: { type: 'integer' }, ai_monthly_quota: { type: 'integer' } } },
        Stipend: { type: 'object', properties: { id: { type: 'integer' }, student_id: { type: 'integer' }, period: { type: 'string' }, amount: { type: 'number' }, base_salary_ref: { type: 'number' }, status: { type: 'integer' }, compliant: { type: 'boolean', nullable: true } } },
        WorkflowState: { type: 'object', properties: { bizType: { type: 'string' }, bizId: { type: 'integer' }, state: { type: 'string' }, stateName: { type: 'string' }, isEnd: { type: 'boolean' }, actions: { type: 'array', items: { type: 'object', properties: { action: { type: 'string' }, name: { type: 'string' }, to_state: { type: 'string' } } } } } },
        RiskRadarDim: { type: 'object', properties: { key: { type: 'string' }, label: { type: 'string' }, value: { type: 'integer' } } },
        ProductOverview: {
          type: 'object',
          required: ['source', 'generatedAt', 'kpis', 'collegeRanking', 'demoFlow'],
          properties: {
            source: { type: 'string', enum: ['mock-public-demo', 'mock-empty-database', 'mock-query-fallback', 'database', 'mixed'] },
            generatedAt: { type: 'string', format: 'date-time' },
            kpis: { type: 'object', additionalProperties: { type: 'number' } },
            collegeRanking: { type: 'array', items: { type: 'object', properties: { collegeName: { type: 'string' }, students: { type: 'integer' }, inPostRate: { type: 'number' }, reportSubmitRate: { type: 'number' }, riskAlerts: { type: 'integer' }, status: { type: 'string', enum: ['excellent', 'normal', 'warning', 'danger'] } } } },
            demoFlow: { type: 'array', items: { type: 'object', properties: { title: { type: 'string' }, description: { type: 'string' }, tag: { type: 'string' } } } },
            metricDefinitions: { type: 'object', additionalProperties: { type: 'string' }, description: '仅登录后的真实统计返回' },
            metricContext: { type: 'object', description: '当前统计范围、时区和口径限制；仅真实统计返回' }
          }
        },
        Error: errSchema,
      },
    },
    security: [{ bearerAuth: [] }],
    paths: {
      '/users/login': { post: { tags: ['认证'], summary: '登录', security: [], requestBody: jsonBody({ $ref: '#/components/schemas/LoginReq' }), responses: { 200: jsonResp('登录成功（返回 token/user/mustChangePassword）', ok()), 401: errResp('用户名或密码错误') } } },
      '/users/register': { post: { tags: ['认证'], summary: '学生自助注册（角色强制为学生）', security: [], requestBody: jsonBody({ $ref: '#/components/schemas/RegisterReq' }), responses: { 201: jsonResp('注册成功', ok()), 409: errResp('用户名已存在') } } },
      '/users/profile': { get: { tags: ['用户'], summary: '当前用户信息', responses: { 200: jsonResp('成功', ok()) } } },
      '/stipends': {
        get: { tags: ['实习报酬'], summary: '报酬台账列表', parameters: [{ name: 'period', in: 'query', schema: { type: 'string' } }, { name: 'page', in: 'query', schema: { type: 'integer' } }], responses: { 200: jsonResp('成功', ok()) } },
        post: { tags: ['实习报酬'], summary: '登记报酬（自动校验≥试用期80%合规）', requestBody: jsonBody({ $ref: '#/components/schemas/StipendCreateReq' }), responses: { 201: jsonResp('已登记（含 compliance）', ok()), 400: errResp('参数校验失败'), 403: errResp('权限不足') } },
      },
      '/stipends/stats': { get: { tags: ['实习报酬'], summary: '发放进度+合规率', responses: { 200: jsonResp('成功', ok()) } } },
      '/ai/status': { get: { tags: ['AI'], summary: 'AI 服务状态(live/demo)', responses: { 200: jsonResp('成功', ok()) } } },
      '/ai/score-log/{id}': { post: { tags: ['AI'], summary: '实习日志智能质检', parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }], responses: { 200: jsonResp('评分+建议（含 isDemo）', ok()) } } },
      '/ai/analyze-risk': { post: { tags: ['AI'], summary: '文本风险研判', requestBody: jsonBody({ type: 'object', properties: { text: { type: 'string' }, log_id: { type: 'integer' } } }), responses: { 200: jsonResp('风险等级+信号', ok()) } } },
      '/bigscreen/gis': { get: { tags: ['监管大屏'], summary: 'GIS 实习分布点位', responses: { 200: jsonResp('成功', ok()) } } },
      '/bigscreen/risk-radar': { get: { tags: ['监管大屏'], summary: '多维风险雷达', responses: { 200: jsonResp('成功', ok({ type: 'object', properties: { dimensions: { type: 'array', items: { $ref: '#/components/schemas/RiskRadarDim' } } } })) } } },
      '/public/product-overview-demo': {
        get: {
          tags: ['产品概览'],
          summary: '公开销售演示概览（固定脱敏样例，不读取学校真实数据库）',
          security: [],
          responses: { 200: jsonResp('固定样例聚合数据', ok({ $ref: '#/components/schemas/ProductOverview' })) }
        }
      },
      '/stats/product-overview': {
        get: {
          tags: ['产品概览'],
          summary: '真实学校产品概览（仅院校/二级学院管理员）',
          parameters: [{ name: 'demo', in: 'query', description: '值为1时允许空库降级为样例聚合数据', schema: { type: 'string', enum: ['1'] } }],
          responses: {
            200: jsonResp('当前租户聚合统计与口径说明', ok({ $ref: '#/components/schemas/ProductOverview' })),
            401: errResp('未登录或令牌无效'),
            403: errResp('当前角色无权查看校级聚合数据')
          }
        }
      },
      '/workflows/defs': { get: { tags: ['流程引擎'], summary: '流程定义列表（管理员）', responses: { 200: jsonResp('成功', ok()) } } },
      '/workflows/def/{bizType}': {
        get: { tags: ['流程引擎'], summary: '取某流程定义', parameters: [{ name: 'bizType', in: 'path', required: true, schema: { type: 'string', example: 'intern_apply' } }], responses: { 200: jsonResp('成功', ok()) } },
        put: { tags: ['流程引擎'], summary: '配置流程定义（状态+流转，配置化核心）', parameters: [{ name: 'bizType', in: 'path', required: true, schema: { type: 'string' } }], responses: { 200: jsonResp('已更新', ok()) } },
      },
      '/workflows/{bizType}/{bizId}': { get: { tags: ['流程引擎'], summary: '单据当前状态+可执行动作+历史', parameters: [{ name: 'bizType', in: 'path', required: true, schema: { type: 'string' } }, { name: 'bizId', in: 'path', required: true, schema: { type: 'integer' } }], responses: { 200: jsonResp('成功', ok({ $ref: '#/components/schemas/WorkflowState' })) } } },
      '/workflows/{bizType}/{bizId}/dispatch': { post: { tags: ['流程引擎'], summary: '驱动流转', parameters: [{ name: 'bizType', in: 'path', required: true, schema: { type: 'string' } }, { name: 'bizId', in: 'path', required: true, schema: { type: 'integer' } }], requestBody: jsonBody({ $ref: '#/components/schemas/WfDispatchReq' }), responses: { 200: jsonResp('流转成功', ok({ $ref: '#/components/schemas/WorkflowState' })), 400: errResp('状态不允许该动作'), 403: errResp('角色无权') } } },
    },
    // 平台运营（根级，单独 server/安全）
    'x-platform-paths-note': '平台运营接口前缀 /api/platform，用 platformAuth；下方为代表性接口',
  };
}

// 平台接口单独并入（避免与 v1 server 前缀混淆，挂在根 server 下）
function withPlatform(spec) {
  spec.paths['/api/platform/tenants'] = {
    get: { tags: ['平台运营(SaaS)'], summary: '租户列表', servers: [{ url: '' }], security: [{ platformAuth: [] }], responses: { 200: jsonResp('成功', ok()), 401: errResp('平台令牌无效') } },
    post: { tags: ['平台运营(SaaS)'], summary: '开通学校（建库+迁移+种管理员）', security: [{ platformAuth: [] }], requestBody: jsonBody({ $ref: '#/components/schemas/ProvisionReq' }), responses: { 201: jsonResp('开通成功（返回初始管理员密码）', ok()), 400: errResp('参数/模式错误'), 409: errResp('code 已存在') } },
  };
  spec.paths['/api/platform/pool-stats'] = { get: { tags: ['平台运营(SaaS)'], summary: '连接池统计（含读副本/分片状态）', security: [{ platformAuth: [] }], responses: { 200: jsonResp('成功', ok()) } } };
  spec.paths['/api/platform/billing'] = { get: { tags: ['平台运营(SaaS)'], summary: '计费对账报告（用量vs配额 + ARR/MRR）', security: [{ platformAuth: [] }], parameters: [{ name: 'period', in: 'query', schema: { type: 'string', example: '2026-06' } }], responses: { 200: jsonResp('成功', ok()) } } };
  spec.paths['/api/platform/billing/refresh'] = { post: { tags: ['平台运营(SaaS)'], summary: '全租户用量聚合（对账前置，逐校切库统计）', security: [{ platformAuth: [] }], responses: { 200: jsonResp('已聚合', ok()) } } };
  spec.paths['/api/platform/supervision'] = { get: { tags: ['平台运营(SaaS)'], summary: '监管局跨校驾驶舱（跨租户实习规模+风险总账）', security: [{ platformAuth: [] }], responses: { 200: jsonResp('成功', ok()) } } };
  spec.paths['/metrics'] = { get: { tags: ['系统'], summary: 'Prometheus 指标', security: [], responses: { 200: { description: 'Prometheus 文本格式' } } } };
  spec.paths['/api/health'] = { get: { tags: ['系统'], summary: '健康检查', security: [], responses: { 200: jsonResp('正常', ok()) } } };
  return spec;
}

module.exports = (baseUrl) => withPlatform(buildSpec(baseUrl));
