<!--
  顶栏「重置演示数据」入口
  ---------------------------------------------------------------
  图标选 RefreshLeft（Element Plus 图标）—— 回退、重来，
  和「重置」的意思对得上。

  为什么放在顶栏：
    它是一个【运维动作】，不是业务操作。
    业务动作在各页面顶栏（新增/导出），运维动作在全局顶栏，
    这样既不干扰各页面的排版，也方便任何时候都能找到。

  为什么平时看不见：
    服务器没配 RESET_TOKEN 时，这个按钮【整个不显示】——
    而不是显示出来点一下报错。功能不存在时，界面也不该有。
-->

<template>
  <button
    v-if="available"
    type="button"
    class="toolBar-icon reset-trigger"
    title="重置演示数据"
    aria-label="重置演示数据"
    @click="open"
  >
    <el-icon><RefreshLeft /></el-icon>
  </button>
  <ResetDataDialog ref="dialogRef" @reset-done="handleResetDone" />
</template>

<script setup lang="ts">
/**
 * =====================================================================
 * 顶栏重置入口
 * =====================================================================
 * 挂载时探一次 /reset/status：
 *   · enabled=false  -> 按钮不渲染（服务器没启用这个功能）
 *   · enabled=true   -> 渲染按钮
 *
 * 探测失败（后端没起 / 网络不通）时也隐藏按钮 ——
 * 宁可少一个入口，也不要给用户一个点了必报错的功能。
 */
import { RefreshLeft } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import ResetDataDialog from '@/components/ResetDataDialog/index.vue'
import { fetchResetStatus } from '@/api/reset'
import { useRouter } from 'vue-router'

const dialogRef = ref<InstanceType<typeof ResetDataDialog> | null>(null)
const available = ref(false)
const router = useRouter()

onMounted(async () => {
  try {
    const status = await fetchResetStatus()
    available.value = !!status.enabled
  } catch {
    available.value = false
  }
})

/** 打开重置弹窗 */
const open = () => {
  dialogRef.value?.open()
}

/**
 * 重置完成后刷新当前页面数据。
 *
 * 为什么要整页 reload 而不是局部刷新：
 *   重置把 7 张表全换了一遍，各列表页的缓存（Pinia / keep-alive）
 *   都可能持有旧数据。整页重载是最不会出错的做法 ——
 *   代价只是多一次白屏，对一个运维动作来说完全可以接受。
 */
const handleResetDone = () => {
  router.go(0)
}
</script>

<style scoped lang="scss">
.reset-trigger {
  padding: 0;
  background-color: transparent;
  border: none;
}
</style>
