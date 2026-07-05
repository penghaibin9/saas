/**
 * 路由登记：P1 各业务模块统一走 ModuleTemplateView（模块模板页），
 * 由 :module 参数 + moduleRegistry 决定加载哪个域数据。后续 P2 可为重模块替换为专用页。
 */
import { MODULES } from './moduleRegistry'

export const MODULE_PATHS = MODULES.filter((m) => m.path !== 'home').map((m) => m.path)
