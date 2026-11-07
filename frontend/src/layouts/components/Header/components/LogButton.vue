<!--
  顶栏「运行日志」入口
  ---------------------------------------------------------------
  图标选 Tickets（Element Plus 图标）—— 一叠单据，正好是「逐条记录」的意思；
  比 Bell（提醒）更贴日志本身的性质，比 Document（文档）更有「流水」感。

  角标：只有出现错误时才亮朱砂数字，正常时不占视觉。
-->

<template>
  <el-badge :value="errorCount" :hidden="errorCount === 0" :max="99" class="log-badge">
    <button
      type="button"
      class="toolBar-icon log-trigger"
      title="运行日志"
      aria-label="运行日志"
      @click="open"
    >
      <el-icon><Tickets /></el-icon>
    </button>
  </el-badge>
  <LogPanel v-model="visible" />
</template>

<script setup lang="ts">
import { Tickets } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import LogPanel from '@/components/LogPanel/index.vue'
import { subscribeLogs, type LogEntry } from '@/utils/logger'

/** 面板是否打开 */
const visible = ref(false)

/** 错误条数（角标） */
const errorCount = ref(0)

let unsubscribe: (() => void) | null = null

onMounted(() => {
  unsubscribe = subscribeLogs((entries: LogEntry[]) => {
    errorCount.value = entries.filter((item) => item.level === 'error').length
  })
})

onBeforeUnmount(() => {
  unsubscribe?.()
  unsubscribe = null
})

/** 打开日志面板 */
const open = () => {
  visible.value = true
}

/** 供外部（比如快捷键）调用 */
const show = computed(() => visible.value)
defineExpose({ show })
</script>

<style scoped lang="scss">
.log-badge {
  margin-right: 6px;

  :deep(.el-badge__content) {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    background-color: var(--seal);
    border-color: var(--paper);
  }
}

.log-trigger {
  padding: 0;
  background-color: transparent;
  border: none;
}
</style>
