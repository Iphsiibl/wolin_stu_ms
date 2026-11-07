/**
 * =====================================================================
 * 演示数据重置的接口封装
 * =====================================================================
 * 对应后端：API/reset_api.py  (router09, 前缀 /reset)
 *
 * 【为什么要把重置做成一个独立模块？】
 * 系统部署到公网后，任何拿到网址的人都能增删改数据。
 * 被软删了、被改坏了字段、被塞了垃圾行 —— 都需要一个
 * 「一键回到初始状态」的出口。
 *
 * 【安全设计】
 * 后端设了三道闸门：口令、确认短语、未配置即关闭。
 * 前端只负责把用户输入送过去，校验逻辑在后端 ——
 * 前端校验只是体验优化，真正的防线不能建在前端。
 * =====================================================================
 */
import { get, post } from '@/api/http'

/** 各表当前行数 */
export type ResetCounts = Record<string, number>

/** 重置功能状态 */
export interface ResetStatus {
  /** 服务器是否启用了重置功能（没配 RESET_TOKEN 就是 false） */
  enabled: boolean
  /** 提示文案 */
  message: string
  /** 当前各表行数 */
  current_counts?: ResetCounts
  /** 种子基线各表行数 */
  baseline_counts?: ResetCounts
  /** 当前总行数 */
  total_current?: number
  /** 基线总行数 */
  total_baseline?: number
  /** 当前是否已经处于基线状态 */
  is_at_baseline?: boolean
}

/** 重置执行结果 */
export interface ResetResult {
  ok: boolean
  message: string
  /** 重置后各表行数 */
  counts: ResetCounts
  /** 每张表是否达到基线 */
  baseline_check: Record<string, boolean>
  /** 是否全部达标 */
  all_match: boolean
  /** 耗时（毫秒） */
  duration_ms: number
}

/**
 * 查询重置功能状态与当前数据量
 *
 * 打开弹窗时先调它，让用户看清「现在多少行 → 重置后多少行」。
 *
 * 注意：适配层（http.ts）会把响应统一包成 {code, message, data, total}，
 * 所以这里取的是 res.data —— 封装层已经把这层拆包做好了，
 * 上层拿到的就是干净的业务对象。
 */
export async function fetchResetStatus() {
  const res = await get<ResetStatus>('/reset/status')
  return res.data
}

/**
 * 执行重置
 *
 * @param token   重置口令（对应服务器环境变量 RESET_TOKEN）
 * @param confirm 确认短语，必须是 'RESET'
 *
 * 口令走请求体而不是 query 参数 —— query 会进 Nginx 访问日志。
 */
export async function executeReset(token: string, confirm: string) {
  const res = await post<ResetResult>('/reset/execute', { token, confirm })
  return res.data
}
