/**
 * =====================================================================
 * 图标解析
 * ---------------------------------------------------------------------
 * 路由表里 meta.icon 写的是字符串（如 'Odometer'），
 * 菜单和面包屑渲染时需要真正的组件，这里做一次转换。
 * =====================================================================
 */
import type { Component } from 'vue'
import { markRaw } from 'vue'
import {
  Avatar,
  Briefcase,
  Document,
  EditPen,
  Notebook,
  Odometer,
  School,
  Service,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'

const ICONS: Record<string, Component> = {
  Odometer,
  User,
  EditPen,
  Briefcase,
  School,
  Avatar,
  TrendCharts,
  // 下面两个是菜单扁平化之后新拆出来的菜单项用的图标
  Service, // 顾问管理（咨询服务）
  Notebook, // 班主任（教案/记事本）
}

/**
 * 按名字取图标组件，取不到就返回默认的文档图标。
 *
 * 【为什么用 markRaw】
 * 图标组件会被塞进 Pinia 的菜单树、页签等响应式对象里，
 * 不 markRaw 的话 Vue 会把组件对象包成响应式代理，
 * 控制台会刷 "Component that was made a reactive object" 告警。
 */
export function resolveIcon(name?: string): Component {
  if (!name) return markRaw(Document)
  return markRaw(ICONS[name] ?? Document)
}
