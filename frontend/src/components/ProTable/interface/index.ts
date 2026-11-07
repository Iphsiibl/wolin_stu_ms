/**
 * =====================================================================
 * ProTable 的类型定义
 * ---------------------------------------------------------------------
 * 移植自 Geeker-Admin（MIT License, Copyright (c) 2022 Halsey）。
 *
 * 相比原版做了三处适配：
 *   1. ProTableProps / ProTableInstance 从 index.vue 挪到这里，
 *      避免 index.vue 与 interface 互相 import 造成的循环依赖；
 *   2. ColumnProps 增加了 slotName（自定义单元格用的插槽名）；
 *   3. 补上了 useTable 用到的表格状态类型（原本在 hooks/interface 里）。
 * =====================================================================
 */
import type { TableColumnCtx } from 'element-plus/es/components/table/src/table-column/defaults'
import type { Ref, VNode } from 'vue'

import type { BreakPoint, Responsive } from '@/components/Grid/interface'

export interface EnumProps {
  label?: string // 选项框显示的文字
  value?: string | number | boolean | any[] // 选项框值
  disabled?: boolean // 是否禁用此选项
  tagType?: string // 当 tag 为 true 时，此选择会指定 tag 显示类型
  children?: EnumProps[] // 为树形选择时，可以通过 children 属性指定子选项
  [key: string]: any
}

export type TypeProps = 'index' | 'selection' | 'radio' | 'expand' | 'sort'

export type SearchType =
  | 'input'
  | 'input-number'
  | 'select'
  | 'select-v2'
  | 'tree-select'
  | 'cascader'
  | 'date-picker'
  | 'time-picker'
  | 'time-select'
  | 'switch'
  | 'slider'

export type SearchRenderScope = {
  searchParam: { [key: string]: any }
  placeholder: string
  clearable: boolean
  options: EnumProps[]
  data: EnumProps[]
}

export type SearchProps = {
  el?: SearchType // 当前项搜索框的类型
  label?: string // 当前项搜索框的 label
  props?: any // 搜索项参数，根据 element plus 官方文档来传递，该属性所有值会透传到组件
  key?: string // 当搜索项 key 不为 prop 属性时，可通过 key 指定
  tooltip?: string // 搜索提示
  order?: number // 搜索项排序（从大到小）
  span?: number // 搜索项所占用的列数，默认为 1 列
  offset?: number // 搜索字段左侧偏移列数
  defaultValue?: string | number | boolean | any[] | Ref<any> // 搜索项默认值
  render?: (scope: SearchRenderScope) => VNode // 自定义搜索内容渲染（tsx语法）
} & Partial<Record<BreakPoint, Responsive>>

export type FieldNamesProps = {
  label: string
  value: string
  children?: string
}

/**
 * el-table 的行数据类型。
 * Element Plus 2.14 的 TableColumnCtx 对行类型有约束，这里保持一致。
 */
export type DefaultRow = Record<PropertyKey, any>

export type RenderScope<T extends DefaultRow = DefaultRow> = {
  row: T
  $index: number
  column: TableColumnCtx<T>
  [key: string]: any
}

export type HeaderRenderScope<T extends DefaultRow = DefaultRow> = {
  $index: number
  column: TableColumnCtx<T>
  [key: string]: any
}

/** 排序方向（与 el-table 的 order 取值保持一致） */
export type SortOrder = 'ascending' | 'descending'

/**
 * ProTable 的默认排序配置。
 *
 * 可以传单条，也可以传多条：
 *   - 单条：{ prop: 'stu_id', order: 'ascending' }
 *   - 多条：[{ prop: 'stu_id', order: 'ascending' }, { prop: 'stu_age', order: 'ascending' }]
 *     多条按数组顺序依次比较（前一条相同时才看后一条），
 *     数组第一条会作为 el-table 的 default-sort（表头箭头落在哪一列）。
 */
export interface ProTableSort {
  /** 排序字段（对应列的 prop） */
  prop: string
  /** 排序方向 */
  order: SortOrder
}

/**
 * 表格列的配置。
 *
 * 【列宽口径 —— 改列宽前先看这段】
 *   Element Plus 的宽度分配规则（见 element-plus 的 table-layout）：
 *     · 写了 `width` 的列 = 固定列，不参与剩余空间分配；
 *     · 只写 `minWidth` 的列 = 弹性列，剩下的空间【按 minWidth 的比例】分给它们；
 *     · 弹性列只剩一列时，那一列独吞全部剩余空间 —— 表格中间会出现一个巨大的空洞。
 *   所以本项目的约定是：
 *     1. 序号列、操作列用 `width` 固定（它们不该被拉长）；
 *     2. 其余内容列一律用 `minWidth`，让空间按比例摊开，表格既铺满又不会失衡；
 *     3. 可排序列的 `minWidth` 不低于 80 —— 表头文字加排序箭头约 50px，
 *        再窄表头会被省略号截成「年..」这种样子。
 */
export interface ColumnProps<T extends DefaultRow = DefaultRow>
  extends Partial<Omit<TableColumnCtx<T>, 'type' | 'children' | 'renderCell' | 'renderHeader'>> {
  type?: TypeProps // 列类型
  tag?: boolean | Ref<boolean> // 是否是标签展示
  isShow?: boolean | Ref<boolean> // 是否显示在表格当中
  isSetting?: boolean | Ref<boolean> // 是否在 ColSetting 中可配置
  search?: SearchProps | undefined // 搜索项配置
  enum?: EnumProps[] | Ref<EnumProps[]> | ((params?: any) => Promise<any>) // 枚举字典
  isFilterEnum?: boolean | Ref<boolean> // 当前单元格值是否根据 enum 格式化（示例：enum 只作为搜索项数据）
  fieldNames?: FieldNamesProps // 指定 label && value && children 的 key 值
  headerRender?: (scope: HeaderRenderScope<T>) => VNode // 自定义表头内容渲染（tsx语法）
  render?: (scope: RenderScope<T>) => VNode | string // 自定义单元格内容渲染（tsx语法）
  _children?: ColumnProps<T>[] // 多级表头
  /** 自定义单元格的插槽名，不填则取 prop 的最后一段 */
  slotName?: string
  /** 是否可排序：true = 前端排序（表头出现排序箭头），'custom' = 自定义（远程）排序 */
  sortable?: boolean | 'custom'
  /** 排序依据字段：不填则用 prop 对应的原始值比较 */
  sortBy?: TableColumnCtx<T>['sortBy']
  /**
   * 自定义排序方法：升序比较器（返回 <0 / 0 / >0），降序由表格自动取反。
   * 原始值不能直接比较时用它兜底（例如日期字符串格式不统一）。
   */
  sortMethod?: TableColumnCtx<T>['sortMethod']
  /** 点击表头时的排序顺序，默认 ['ascending', 'descending', null] */
  sortOrders?: TableColumnCtx<T>['sortOrders']
}

/* ---------------------------------------------------------------------
 * useTable 用到的表格状态
 * ------------------------------------------------------------------ */

/** 分页信息 */
export interface Pageable {
  pageNum: number
  pageSize: number
  total: number
}

/** useTable 内部的表格状态 */
export interface TableStateProps {
  tableData: any[]
  pageable: Pageable
  searchParam: { [key: string]: any }
  searchInitParam: { [key: string]: any }
  totalParam: { [key: string]: any }
}

/* ---------------------------------------------------------------------
 * ProTable 自身的 props / 实例类型
 * ------------------------------------------------------------------ */

/** ProTable 的 props */
export interface ProTableProps {
  columns: ColumnProps[] // 列配置项  ==> 必传
  data?: any[] // 静态 table data 数据，若存在则不会使用 requestApi 返回的 data ==> 非必传
  requestApi?: (params: any) => Promise<any> // 请求表格数据的 api ==> 非必传
  requestAuto?: boolean // 是否自动执行请求 api ==> 非必传（默认为true）
  requestError?: (params: any) => void // 表格 api 请求错误监听 ==> 非必传
  dataCallback?: (data: any) => any // 返回数据的回调函数，可以对数据进行处理 ==> 非必传
  title?: string // 表格标题 ==> 非必传
  pagination?: boolean // 是否需要分页组件 ==> 非必传（默认为true）
  initParam?: any // 初始化请求参数 ==> 非必传（默认为{}）
  border?: boolean // 是否带有纵向边框 ==> 非必传（默认为true）
  toolButton?: ('refresh' | 'setting' | 'search')[] | boolean // 是否显示表格功能按钮 ==> 非必传（默认为true）
  rowKey?: string // 行数据的 Key，用来优化 Table 的渲染 ==> 非必传（默认为 id）
  searchCol?: number | Record<BreakPoint, number> // 表格搜索项 每列占比配置 ==> 非必传 { xs: 1, sm: 2, md: 2, lg: 3, xl: 4 }
  /** 表格加载中（对应原来 el-table 上的 v-loading） */
  loading?: boolean
  /**
   * 默认排序：传单条 { prop, order } 或多条（按数组顺序依次比较）。
   * 不传则不排序（对现有调用方零破坏）。
   */
  defaultSort?: ProTableSort | ProTableSort[]
  /**
   * 窄表模式：列少的页面（顾问管理、班主任）把表格收窄居中。
   * 铺满整屏宽的话，几列内容摊在巨大的纸面上，中间全是空白，反而不像一张册页。
   */
  narrow?: boolean
}

/** ProTable 实例暴露出去的状态与方法 */
export interface ProTableInstance {
  element: Ref<any>
  tableData: Ref<any[]>
  radio: Ref<string>
  pageable: Ref<Pageable>
  searchParam: Ref<{ [key: string]: any }>
  searchInitParam: Ref<{ [key: string]: any }>
  isSelected: Ref<boolean>
  selectedList: Ref<{ [key: string]: any }[]>
  selectedListIds: Ref<string[]>
  enumMap: Ref<Map<string, { [key: string]: any }[]>>
  getTableList: () => Promise<void>
  search: () => void
  reset: () => void
  handleSizeChange: (val: number) => void
  handleCurrentChange: (val: number) => void
  clearSelection: () => void
}
