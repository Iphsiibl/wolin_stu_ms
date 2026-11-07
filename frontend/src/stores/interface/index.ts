/**
 * =====================================================================
 * 布局 / 菜单 / 页签 相关的类型定义
 * =====================================================================
 */

/** 菜单项的 meta 信息 */
export interface MenuMeta {
  /** 菜单文字 */
  title: string
  /** 菜单图标（Element Plus 图标组件） */
  icon?: unknown
  /** 外链地址 */
  isLink?: string
  /** 是否在菜单里隐藏 */
  isHide?: boolean
  /** 是否固定在页签栏 */
  isAffix?: boolean
  /** 是否缓存页面 */
  isKeepAlive?: boolean
  /** 是否全屏（不显示页签） */
  isFull?: boolean
  /** 高亮的菜单路径 */
  activeMenu?: string
}

/** 菜单树节点 */
export interface MenuOptions {
  /** 路由路径 */
  path: string
  /** 路由名 */
  name?: string
  meta: MenuMeta
  children?: MenuOptions[]
}

/** 页签项 */
export interface TabsMenuProps {
  /** 页签图标（Element Plus 图标组件） */
  icon?: unknown
  /** 页签标题 */
  title: string
  /** 页签对应的路由全路径 */
  path: string
  /** 路由名 */
  name?: string
  /** 是否可关闭 */
  close: boolean
  /** 是否缓存（路由没配就是 undefined，即不缓存） */
  isKeepAlive?: boolean
}

/** Element Plus 组件尺寸 */
export type AssemblySizeType = 'default' | 'small' | 'large'
