/**
 * =====================================================================
 * 表格辅助工具
 * ---------------------------------------------------------------------
 * 配合 src/components/ProTable 使用（该组件移植自 Geeker-Admin，MIT）。
 * =====================================================================
 */

/** 生成一个带横杠的 uuid（给 el-table 做 id，用于列拖拽排序） */
export function generateUUID(): string {
  let uuid = ''
  for (let i = 0; i < 32; i++) {
    const random = (Math.random() * 16) | 0
    if (i === 8 || i === 12 || i === 16 || i === 20) uuid += '-'
    uuid += (i === 12 ? 4 : i === 16 ? (random & 3) | 8 : random).toString(16)
  }
  return uuid
}

/**
 * 取属性名的最后一段。
 * 例如 handleProp('a.b.c') -> 'c'
 */
export function handleProp(prop: string): string {
  const propArr = prop.split('.')
  if (propArr.length === 1) return prop
  return propArr[propArr.length - 1]
}

/**
 * 把后端归一化后的结果，转成 ProTable 期望的分页形状。
 *
 * 后端经过 src/api/http.ts 归一化后统一是 {code, message, data, total}，
 * 而 ProTable 内部约定 api 返回 { data: { list, total } }。
 *
 * 用法：
 *   const api = async () => toTableResult(await fetchAllStudents())
 */
export function toTableResult<T>(res: {
  data?: T[] | null
  total?: number
}): { data: { list: T[]; total: number } } {
  const list = Array.isArray(res.data) ? res.data : []
  return {
    data: {
      list,
      total: typeof res.total === 'number' ? res.total : list.length,
    },
  }
}
