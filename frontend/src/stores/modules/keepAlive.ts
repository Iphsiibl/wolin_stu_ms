/**
 * =====================================================================
 * 页面缓存（keep-alive）名单
 * ---------------------------------------------------------------------
 * 对应 Geeker-Admin 的 stores/modules/keepAlive.ts。
 * =====================================================================
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useKeepAliveStore = defineStore('app-keep-alive', () => {
  /** 需要缓存的页面路径（与 keep-alive 的 include 名称一致） */
  const keepAliveName = ref<string[]>([])

  function addKeepAliveName(name: string) {
    if (!keepAliveName.value.includes(name)) {
      keepAliveName.value.push(name)
    }
  }

  function removeKeepAliveName(name: string) {
    keepAliveName.value = keepAliveName.value.filter((item) => item !== name)
  }

  function setKeepAliveName(names: string[]) {
    keepAliveName.value = names
  }

  return {
    keepAliveName,
    addKeepAliveName,
    removeKeepAliveName,
    setKeepAliveName,
  }
})
