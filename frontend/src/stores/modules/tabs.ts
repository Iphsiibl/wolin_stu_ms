/**
 * =====================================================================
 * 页签（多标签页）状态
 * ---------------------------------------------------------------------
 * 对应 Geeker-Admin 的 stores/modules/tabs.ts。
 * =====================================================================
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import type { TabsMenuProps } from '@/stores/interface'
import { useKeepAliveStore } from '@/stores/modules/keepAlive'

export const useTabsStore = defineStore('app-tabs', () => {
  const router = useRouter()
  const keepAliveStore = useKeepAliveStore()

  /** 已打开的页签列表 */
  const tabsMenuList = ref<TabsMenuProps[]>([])

  /** 添加页签（已存在则忽略） */
  function addTabs(tabItem: TabsMenuProps) {
    if (tabsMenuList.value.every((item) => item.path !== tabItem.path)) {
      tabsMenuList.value.push(tabItem)
    }
    if (!keepAliveStore.keepAliveName.includes(tabItem.path) && tabItem.isKeepAlive) {
      keepAliveStore.addKeepAliveName(tabItem.path)
    }
  }

  /** 关闭页签；关的是当前页时，自动跳到相邻页签 */
  function removeTabs(tabPath: string, isCurrent = true) {
    if (isCurrent) {
      tabsMenuList.value.forEach((item, index) => {
        if (item.path !== tabPath) return
        const nextTab = tabsMenuList.value[index + 1] || tabsMenuList.value[index - 1]
        if (!nextTab) return
        router.push(nextTab.path)
      })
    }

    const tabItem = tabsMenuList.value.find((item) => item.path === tabPath)
    if (tabItem?.isKeepAlive) {
      keepAliveStore.removeKeepAliveName(tabItem.path)
    }

    tabsMenuList.value = tabsMenuList.value.filter((item) => item.path !== tabPath)
  }

  /** 关闭左侧 / 右侧的页签 */
  function closeTabsOnSide(path: string, type: 'left' | 'right') {
    const currentIndex = tabsMenuList.value.findIndex((item) => item.path === path)
    if (currentIndex === -1) return

    const range = type === 'left' ? [0, currentIndex] : [currentIndex + 1, tabsMenuList.value.length]
    tabsMenuList.value = tabsMenuList.value.filter(
      (item, index) => index < range[0] || index >= range[1] || !item.close,
    )

    const keepAliveList = tabsMenuList.value.filter((item) => item.isKeepAlive)
    keepAliveStore.setKeepAliveName(keepAliveList.map((item) => item.path))
  }

  /** 关闭除当前页签外的其它可关闭页签 */
  function closeMultipleTab(tabsMenuValue?: string) {
    tabsMenuList.value = tabsMenuList.value.filter(
      (item) => item.path === tabsMenuValue || !item.close,
    )

    const keepAliveList = tabsMenuList.value.filter((item) => item.isKeepAlive)
    keepAliveStore.setKeepAliveName(keepAliveList.map((item) => item.path))
  }

  /** 整体替换页签列表（拖拽排序时用） */
  function setTabs(newTabsMenuList: TabsMenuProps[]) {
    tabsMenuList.value = newTabsMenuList
  }

  /** 修改当前页签标题 */
  function setTabsTitle(title: string) {
    tabsMenuList.value.forEach((item) => {
      if (item.path === router.currentRoute.value.fullPath) item.title = title
    })
  }

  return {
    tabsMenuList,
    addTabs,
    removeTabs,
    closeTabsOnSide,
    closeMultipleTab,
    setTabs,
    setTabsTitle,
  }
})
