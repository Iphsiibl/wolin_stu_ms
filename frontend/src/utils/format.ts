/**
 * =====================================================================
 * 通用工具函数
 * =====================================================================
 */

/**
 * 把后端返回的日期字符串格式化成 "YYYY-MM-DD"。
 *
 * 后端返回的是 ISO 格式："2022-09-01T00:00:00"，
 * 直接显示太长了，表格里只取日期部分就够。
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  return value.split('T')[0]
}

/**
 * 格式化金额：27740 -> "27,740"
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return value.toLocaleString('zh-CN')
}

/**
 * 格式化百分比，保留一位小数。
 */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(1)}%`
}

/**
 * 就业时长：把天数换算成"X个月Y天"这种好读的文案。
 */
export function formatDuration(days: number | null | undefined): string {
  if (days === null || days === undefined) return '-'
  if (days < 0) return '-'
  const months = Math.floor(days / 30)
  const restDays = days % 30
  if (months === 0) return `${restDays} 天`
  if (restDays === 0) return `${months} 个月`
  return `${months} 个月 ${restDays} 天`
}

/**
 * 性别对应的标签颜色。
 *
 * 【注意】必须始终返回一个合法的 el-tag type，
 * 空字符串会触发 Element Plus 的 prop 校验告警（Invalid prop: type）。
 *
 * 男 = 靛蓝淡底（primary），女 = 淡紫淡底（由 is-female 类覆盖）。
 * 这套「靛=男 / 紫=女」和看板、统计分析页的图表配色是同一套，
 * 避免表格和图表各说各话。刻意不用 danger（朱砂）——
 * 朱砂在这套设计里只表示「激活 / 预警 / 删除」，
 * 用在性别上会让人误以为女学员是异常项。
 */
export function sexTagType(sex: string): 'danger' | 'info' | 'primary' {
  if (sex === '男') return 'primary'
  return 'info'
}

/** 女生标签的额外 class，用来换成淡紫底 */
export function sexTagClass(sex: string): string {
  return sex === '女' ? 'is-female' : ''
}

/**
 * 分数对应的标签颜色：>= 80 优秀，>= 60 及格，否则不及格。
 */
export function scoreTagType(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}
