<!--
  演示数据重置按钮
  ---------------------------------------------------------------
  一键把数据库恢复到「种子基线」（200 学生 / 600 成绩 / 134 就业 …）。

  为什么需要它：
    系统部署到公网后，任何拿到网址的人都能增删改数据。
    被人软删了、被改了字段值、被塞了垃圾行 ——
    都需要一个回到初始状态的出口。

  为什么按钮要「口令 + 确认短语」两道：
    重置是破坏性操作。口令防外人，确认短语防手滑。
    真正的校验在后端，前端这两道只是体验层。

  设计取向（教务墨册）：
    · 弹窗沿用册页面板的语言：墨色抬头 + 楷体标题
    · 破坏性操作用朱砂，这是全局「一色一义」的约定
    · 重置前后行数并排显示，让人一眼看清会发生什么
-->

<template>
  <el-dialog
    v-model="visible"
    title="重置演示数据"
    width="min(520px, 92vw)"
    append-to-body
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <!-- —— 状态未启用 —— -->
    <el-alert
      v-if="loaded && !status.enabled"
      type="warning"
      :closable="false"
      show-icon
      title="重置功能未启用"
      description="服务器没有配置 RESET_TOKEN 环境变量，此功能已关闭。"
    />

    <template v-else>
      <!-- —— 警告 —— -->
      <el-alert
        type="error"
        :closable="false"
        show-icon
        title="此操作会清空当前库里的全部数据"
        description="包括你新添加的记录。被软删、被改坏、被插入的垃圾行都会一并消失。"
      />

      <!-- —— 前后对比 —— -->
      <div class="reset-compare">
        <div class="reset-compare-col">
          <div class="reset-compare-label">重置前</div>
          <div class="reset-compare-n">{{ status.total_current ?? '—' }}</div>
          <div class="reset-compare-unit">行</div>
        </div>
        <el-icon class="reset-arrow"><Right /></el-icon>
        <div class="reset-compare-col is-target">
          <div class="reset-compare-label">重置后</div>
          <div class="reset-compare-n">{{ status.total_baseline ?? '—' }}</div>
          <div class="reset-compare-unit">行</div>
        </div>
      </div>

      <!-- —— 各表明细 —— -->
      <el-table
        v-if="hasCountDetail"
        :data="countRows"
        size="small"
        class="reset-table"
        border
      >
        <el-table-column prop="label" label="数据表" />
        <el-table-column prop="current" label="当前" align="right" width="80" />
        <el-table-column prop="baseline" label="基线" align="right" width="80" />
        <el-table-column label="差异" align="right" width="80">
          <template #default="{ row }">
            <span :class="row.diff === 0 ? 'is-same' : 'is-diff'">
              {{ row.diff === 0 ? '一致' : (row.diff > 0 ? '+' + row.diff : row.diff) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <!-- —— 已处于基线 —— -->
      <el-alert
        v-if="status.is_at_baseline"
        type="success"
        :closable="false"
        show-icon
        title="当前数据已经处于基线状态"
        description="无需重置。"
      />

      <!-- —— 口令与确认 —— -->
      <el-form label-position="top" class="reset-form">
        <el-form-item label="重置口令">
          <el-input
            v-model="token"
            type="password"
            show-password
            placeholder="服务器配置的 RESET_TOKEN"
            autocomplete="off"
            @keyup.enter="handleReset"
          />
        </el-form-item>
        <el-form-item label="确认短语">
          <el-input
            v-model="confirm"
            placeholder="输入 RESET 以确认"
            autocomplete="off"
            @keyup.enter="handleReset"
          />
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        v-if="loaded && status.enabled"
        type="danger"
        :loading="loading"
        :disabled="!canReset"
        @click="handleReset"
      >
        确认重置
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * =====================================================================
 * 演示数据重置按钮
 * =====================================================================
 * 状态机很简单，三种状态：
 *   未打开 → 打开时拉一次 /reset/status → 空闲 / 执行中
 *
 * 校验分两层：
 *   前端（这里）：确认短语必须是 RESET —— 只是少点一次鼠标
 *   后端（权威）：口令 + 确认短语 + 未配置即关闭
 * 前端校验被绕过也没关系，后端会挡住。
 */
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Right } from '@element-plus/icons-vue'

import { executeReset, fetchResetStatus, type ResetStatus } from '@/api/reset'

/** 表名的中文标签 */
const TABLE_LABELS: Record<string, string> = {
  student_info: '学生信息',
  scores: '学生成绩',
  employment: '就业信息',
  clazz: '班级',
  class_teacher: '班主任',
  teacher: '授课老师',
  agent: '招生顾问',
}

const visible = ref(false)
const loading = ref(false)
const loaded = ref(false)
const token = ref('')
const confirm = ref('')
const status = ref<ResetStatus>({ enabled: false, message: '' })

/** 各表明细（当前 vs 基线） */
const countRows = computed(() => {
  const cur = status.value.current_counts
  const base = status.value.baseline_counts
  if (!cur || !base) return []
  return Object.keys(base).map((table) => {
    const c = cur[table] ?? 0
    const b = base[table] ?? 0
    return {
      label: TABLE_LABELS[table] ?? table,
      current: c,
      baseline: b,
      diff: c - b,
    }
  })
})

const hasCountDetail = computed(() => countRows.value.length > 0)

/** 前端的两道校验：口令非空 + 确认短语正确 */
const canReset = computed(() => {
  return token.value.trim().length > 0 && confirm.value === 'RESET'
})

/** 打开弹窗时拉一次状态 */
async function handleOpen() {
  loaded.value = false
  confirm.value = ''
  try {
    // fetchResetStatus 已经把适配层的包装拆掉了，直接就是业务对象
    status.value = await fetchResetStatus()
  } catch (e) {
    status.value = { enabled: false, message: '无法获取重置状态' }
    ElMessage.error('无法获取重置状态，请稍后再试')
  } finally {
    loaded.value = true
  }
}

/** 执行重置 */
async function handleReset() {
  if (!canReset.value) {
    ElMessage.warning('请填写口令，并输入确认短语 RESET')
    return
  }

  // 二次确认：这是不可逆的破坏性操作
  try {
    await ElMessageBox.confirm(
      `将清空当前 ${status.value.total_current ?? '?'} 行数据，并恢复到 ${status.value.total_baseline ?? '?'} 行基线状态。此操作不可撤销。`,
      '确认重置演示数据？',
      {
        type: 'warning',
        confirmButtonText: '确定重置',
        cancelButtonText: '再想想',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    // 用户点了「再想想」
    return
  }

  loading.value = true
  try {
    const result = await executeReset(token.value.trim(), confirm.value)
    ElMessage.success(result.message || '重置成功')
    visible.value = false
    token.value = ''

    // 通知外层刷新页面数据
    emit('reset-done')
  } catch (e) {
    // 错误提示已由 http 拦截器统一弹出，这里不再重复
  } finally {
    loading.value = false
  }
}

const emit = defineEmits<{
  (e: 'reset-done'): void
}>()

defineExpose({
  /** 供父组件打开弹窗 */
  open: () => {
    visible.value = true
  },
})
</script>

<style scoped lang="scss">
/* ---------------------------------------------------------------------
 * 前后对比
 * ------------------------------------------------------------------ */
.reset-compare {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  margin: 18px 0;
  padding: 16px;
  background: var(--wash, #f6f8fa);
  border: 1px solid var(--rule-soft, #e9edf1);
  border-radius: 4px;
}

.reset-compare-col {
  text-align: center;
  min-width: 84px;
}

.reset-compare-label {
  font-size: 12px;
  color: var(--text-sub, #6b7a89);
  margin-bottom: 4px;
}

.reset-compare-n {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--text-ink, #16212d);
}

.reset-compare-col.is-target .reset-compare-n {
  color: var(--seal, #c0392b);
}

.reset-compare-unit {
  font-size: 11px;
  color: var(--text-mute, #97a3af);
}

.reset-arrow {
  color: var(--text-mute, #97a3af);
  font-size: 20px;
}

/* ---------------------------------------------------------------------
 * 明细表
 * ------------------------------------------------------------------ */
.reset-table {
  margin-bottom: 16px;
}

.is-same {
  color: var(--text-mute, #97a3af);
}

.is-diff {
  color: var(--seal, #c0392b);
  font-family: Consolas, 'Courier New', monospace;
}

/* ---------------------------------------------------------------------
 * 表单
 * ------------------------------------------------------------------ */
.reset-form {
  margin-top: 4px;
}
</style>
