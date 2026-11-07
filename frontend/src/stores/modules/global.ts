/**
 * =====================================================================
 * 全局状态（侧边栏折叠、面包屑、页签、页脚等布局开关）
 * ---------------------------------------------------------------------
 * 对应 Geeker-Admin 的 stores/modules/global.ts，
 * 去掉了本项目用不到的主题色 / 暗黑模式 / 水印等设置项。
 * 状态会写进 localStorage，刷新后保留。
 * =====================================================================
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'stu_ms_global_state'

/** 需要持久化的字段 */
interface PersistedState {
  isCollapse: boolean
  accordion: boolean
  breadcrumb: boolean
  breadcrumbIcon: boolean
  tabs: boolean
  tabsIcon: boolean
  footer: boolean
}

/** 可以通过 setGlobalState 设置的开关（都是布尔量） */
type SettableKey =
  | 'isCollapse'
  | 'accordion'
  | 'breadcrumb'
  | 'breadcrumbIcon'
  | 'tabs'
  | 'tabsIcon'
  | 'footer'
  | 'maximize'

export const useGlobalStore = defineStore('app-global', () => {
  /** 侧边栏是否折叠 */
  const isCollapse = ref(false)
  /** 手风琴模式：一次只展开一个菜单 */
  const accordion = ref(true)
  /** 是否显示面包屑 */
  const breadcrumb = ref(true)
  /** 是否显示面包屑图标 */
  const breadcrumbIcon = ref(true)
  /** 是否显示页签栏 */
  const tabs = ref(true)
  /** 是否显示页签图标 */
  const tabsIcon = ref(true)
  /** 是否显示页脚 */
  const footer = ref(true)
  /** 页面是否最大化（隐藏框架只留内容） */
  const maximize = ref(false)
  /** 布局类型（本项目固定用竖向布局） */
  const layout = ref('vertical')

  /* --------------------- 持久化 --------------------- */
  function persist() {
    const data: PersistedState = {
      isCollapse: isCollapse.value,
      accordion: accordion.value,
      breadcrumb: breadcrumb.value,
      breadcrumbIcon: breadcrumbIcon.value,
      tabs: tabs.value,
      tabsIcon: tabsIcon.value,
      footer: footer.value,
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {
      // localStorage 不可用就忽略，不影响使用
    }
  }

  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const data = JSON.parse(raw) as Partial<PersistedState>
      if (typeof data.isCollapse === 'boolean') isCollapse.value = data.isCollapse
      if (typeof data.accordion === 'boolean') accordion.value = data.accordion
      if (typeof data.breadcrumb === 'boolean') breadcrumb.value = data.breadcrumb
      if (typeof data.breadcrumbIcon === 'boolean') breadcrumbIcon.value = data.breadcrumbIcon
      if (typeof data.tabs === 'boolean') tabs.value = data.tabs
      if (typeof data.tabsIcon === 'boolean') tabsIcon.value = data.tabsIcon
      if (typeof data.footer === 'boolean') footer.value = data.footer
    } catch {
      // 数据坏了就用默认值
    }
  }

  restore()

  /** 统一设置状态并持久化（maximize 不持久化，它只在当前会话有效） */
  function setGlobalState(key: SettableKey, value: boolean) {
    if (key === 'isCollapse') isCollapse.value = value
    if (key === 'accordion') accordion.value = value
    if (key === 'breadcrumb') breadcrumb.value = value
    if (key === 'breadcrumbIcon') breadcrumbIcon.value = value
    if (key === 'tabs') tabs.value = value
    if (key === 'tabsIcon') tabsIcon.value = value
    if (key === 'footer') footer.value = value
    if (key === 'maximize') maximize.value = value
    persist()
  }

  return {
    isCollapse,
    accordion,
    breadcrumb,
    breadcrumbIcon,
    tabs,
    tabsIcon,
    footer,
    maximize,
    layout,
    setGlobalState,
  }
})
