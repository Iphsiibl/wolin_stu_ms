/**
 * =====================================================================
 * ProTable 配套的单元格工具函数
 * ---------------------------------------------------------------------
 * 移植自 Geeker-Admin（MIT License, Copyright (c) 2022 Halsey）的
 * src/utils/index.ts，只抽出 ProTable 真正用到的几个纯函数。
 *
 * 【为什么不直接放在 utils/table.ts】
 * utils/table.ts 已经被项目占用（generateUUID / handleProp / toTableResult），
 * 而 Geeker 的 utils/index.ts 里混了大量本项目用不到的东西（路由、菜单、主题…），
 * 所以把 ProTable 需要的那部分单独落一份，行为与原版保持一致。
 * =====================================================================
 */
import type { Ref } from 'vue'

import type { ColumnProps, ProTableSort } from '@/components/ProTable/interface'

/** 判断是否数组 */
export function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value)
}

/**
 * 格式化表格单元格的值：
 *   - 数组用 " / " 拼接
 *   - null / undefined 显示 "--"
 */
export function formatValue(callValue: any): string {
  if (isArray(callValue)) return callValue.length ? callValue.join(' / ') : '--'
  return callValue ?? '--'
}

/**
 * 支持多级嵌套的 prop（如 "user.name"），取不到值时返回 "--"
 */
export function handleRowAccordingToProp(row: { [key: string]: any }, prop: string): any {
  if (!prop.includes('.')) return row[prop] ?? '--'
  prop.split('.').forEach((item) => (row = row[item] ?? '--'))
  return row
}

/** 枚举项的字段名映射（label / value / children 对应的 key） */
export interface FieldNames {
  label: string
  value: string
  children?: string
}

/**
 * 根据枚举列表格式化单元格的值。
 * type === 'tag' 时返回 tagType，否则返回 label。
 */
export function filterEnum(
  callValue: any,
  enumData?: any,
  fieldNames?: FieldNames,
  type?: 'tag',
): string {
  const value = fieldNames?.value ?? 'value'
  const label = fieldNames?.label ?? 'label'
  const children = fieldNames?.children ?? 'children'
  let filterData: { [key: string]: any } = {}
  if (Array.isArray(enumData)) filterData = findItemNested(enumData, callValue, value, children)
  if (type === 'tag') {
    return filterData?.tagType ? filterData.tagType : ''
  }
  return filterData ? filterData[label] : '--'
}

/** 递归查找 callValue 对应的枚举项 */
export function findItemNested(
  enumData: any,
  callValue: any,
  value: string,
  children: string,
): any {
  return enumData.reduce((accumulator: any, current: any) => {
    if (accumulator) return accumulator
    if (current[value] === callValue) return current
    if (current[children]) return findItemNested(current[children], callValue, value, children)
  }, null)
}

/**
 * 判断一个值是不是 Ref。
 * 列配置里的 isShow / tag 允许写成 ref，这里统一拆包。
 */
export function isRefValue<T>(value: unknown): value is Ref<T> {
  return typeof value === 'object' && value !== null && 'value' in value
}

/**
 * 列配置里「ProTable 自己用的字段」。
 * 这些字段不是 el-table-column 的 prop，透传过去会变成非法 DOM 属性，
 * 所以渲染列之前要剔掉。
 */
export const CUSTOM_COLUMN_KEYS = [
  'tag',
  'search',
  'enum',
  'isShow',
  'isSetting',
  'isFilterEnum',
  'fieldNames',
  'headerRender',
  'render',
  '_children',
  'slotName',
] as const

/**
 * 从列配置里挑出能安全传给 el-table-column 的属性。
 */
export function pickColumnAttrs(
  item: object,
  extraOmit: readonly string[] = [],
): Record<string, any> {
  const attrs: Record<string, any> = {}
  const source = item as Record<string, any>
  for (const key of Object.keys(source)) {
    const value = source[key]
    if (value === undefined) continue
    if ((CUSTOM_COLUMN_KEYS as readonly string[]).includes(key)) continue
    if (extraOmit.includes(key)) continue
    attrs[key] = value
  }
  return attrs
}

/* ---------------------------------------------------------------------
 * 排序
 * ------------------------------------------------------------------
 * 【为什么 ProTable 要自己再排一遍】
 *
 * el-table 的内置排序有两个限制：
 *   1. 一次只能排一列（sortingColumn 是单个值）；
 *   2. 只对「交给表格的那份数据」排序。
 *
 * 而 ProTable 的静态数据模式是【先分页切片、再交给表格】，
 * 所以如果只依赖 el-table 的 default-sort：
 *   - 页面打开时确实排了，但只排了当前这一页，翻页后顺序就乱；
 *   - 多列默认排序（学号 → 年龄 → 入学时间）也表达不了。
 *
 * 因此 ProTable 在把数据交给表格之前，先按规则把【整份数据】排一次，
 * 再切片；el-table 的 default-sort 只负责表头箭头和点击交互。
 * ------------------------------------------------------------------ */

/**
 * 把 defaultSort 配置统一成规则数组。
 * 单条 { prop, order } 与多条数组等价，非法项（没有 prop）会被丢掉。
 */
export function normalizeSortRules(sort?: ProTableSort | ProTableSort[]): ProTableSort[] {
  if (!sort) return []
  const list = Array.isArray(sort) ? sort : [sort]
  return list
    .filter((item) => !!item?.prop)
    .map((item) => ({
      prop: item.prop,
      order: item.order === 'descending' ? ('descending' as const) : ('ascending' as const),
    }))
}

/** 取排序字段的值（兼容 prop 为 a.b 的情况） */
function getSortValue(row: any, prop: string): any {
  if (!prop.includes('.')) return row?.[prop]
  return prop.split('.').reduce((acc: any, key: string) => acc?.[key], row)
}

/**
 * 两个原始值的比较：
 *   - 数字按数值大小比；
 *   - 字符串按字典序比（日期若是 'YYYY-MM-DD HH:MM:SS' 这类定长格式，字典序即时间序）；
 *   - 空值（undefined / null / ''）统一排在最后。
 */
export function compareSortValue(a: any, b: any): number {
  const aEmpty = a === undefined || a === null || a === ''
  const bEmpty = b === undefined || b === null || b === ''
  if (aEmpty || bEmpty) {
    if (aEmpty && bEmpty) return 0
    return aEmpty ? 1 : -1
  }
  if (typeof a === 'number' && typeof b === 'number') return a - b
  const valueA = String(a)
  const valueB = String(b)
  return valueA < valueB ? -1 : valueA > valueB ? 1 : 0
}

/**
 * 按单条规则比较两行（升序比较器，方向由调用方处理）。
 * 优先级：列的 sortMethod > 列的 sortBy > 字段原始值。
 */
function compareRowsByRule(a: any, b: any, rule: ProTableSort, column?: ColumnProps): number {
  // 自定义排序方法优先（它本身就是升序比较器）
  if (column?.sortMethod) return column.sortMethod(a, b)

  // sortBy 指定了别的字段，就按那个字段比
  const sortBy = column?.sortBy
  if (typeof sortBy === 'string') {
    return compareSortValue(getSortValue(a, sortBy), getSortValue(b, sortBy))
  }
  if (Array.isArray(sortBy)) {
    for (const key of sortBy) {
      if (typeof key !== 'string') break
      const diff = compareSortValue(getSortValue(a, key), getSortValue(b, key))
      if (diff !== 0) return diff
    }
    return 0
  }

  // 兜底：按字段原始值比
  return compareSortValue(getSortValue(a, rule.prop), getSortValue(b, rule.prop))
}

/**
 * 按规则给行数据排序（多列依次比较）。
 *
 * rules 按优先级排列：前一条相同时才看后一条（等价于 SQL 的 ORDER BY a, b）。
 * 没有规则时原样返回（不复制数组，避免无谓的渲染开销）。
 */
export function sortRowsByRules<T extends Record<string, any>>(
  rows: T[],
  rules: ProTableSort[],
  columns: ColumnProps[] = [],
): T[] {
  if (!rules.length || !rows.length) return rows
  return rows.slice().sort((a, b) => {
    for (const rule of rules) {
      const column = columns.find((col) => col.prop === rule.prop)
      const direction = rule.order === 'descending' ? -1 : 1
      const diff = compareRowsByRule(a, b, rule, column)
      if (diff !== 0) return diff * direction
    }
    return 0
  })
}
