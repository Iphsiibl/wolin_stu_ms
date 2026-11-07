<!--
  运行日志面板
  ---------------------------------------------------------------
  顶栏「运行日志」图标点开的册页。

  设计取向（教务墨册）：
    · 抬头用墨色压边 + 楷体标题，和其它册页面板同一套语言
    · 每条日志左边一道竖条表示级别，颜色沿用全局「一色一义」
      朱砂=错误 / 赭=警告 / 青=请求 / 靛=信息 / 灰=调试
    · 时间、级别、来源用等宽字体，像台账一样对齐
  最新的一条永远在最上面 —— 出错的时候不用往下翻。
-->

<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    size="min(580px, 92vw)"
    class="log-drawer"
    :with-header="false"
    append-to-body
  >
    <div class="log-panel">
      <!-- —— 册页抬头 —— -->
      <header class="log-head">
        <div class="log-head-lf">
          <span class="log-seal">
            <el-icon><Tickets /></el-icon>
          </span>
          <div class="log-head-text">
            <div class="log-title">运行日志</div>
            <div class="log-sub">前端可观测日志 · 控制台 / 接口 / 运行时异常</div>
          </div>
        </div>
        <div class="log-head-ri">
          <el-button text size="small" @click="handleCopy">复制</el-button>
          <el-button text size="small" @click="handleClear">清空</el-button>
          <el-icon class="log-close" title="关闭" @click="close"><Close /></el-icon>
        </div>
      </header>

      <!-- —— 过滤条 —— -->
      <div class="log-bar">
        <div class="log-chips">
          <button
            type="button"
            :class="['log-chip', { 'is-on': activeLevels.size === 0 }]"
            @click="activeLevels.clear()"
          >
            全部<span class="log-chip-n">{{ logs.length }}</span>
          </button>
          <button
            v-for="lv in LOG_LEVELS"
            :key="lv"
            type="button"
            :class="['log-chip', `is-${lv}`, { 'is-on': activeLevels.has(lv) }]"
            @click="toggleLevel(lv)"
          >
            {{ LEVEL_LABELS[lv] }}<span class="log-chip-n">{{ countOf(lv) }}</span>
          </button>
        </div>
        <el-input
          v-model="keyword"
          class="log-search"
          size="small"
          placeholder="搜索日志内容"
          clearable
          :prefix-icon="Search"
        />
      </div>

      <!-- —— 日志正文 —— -->
      <div class="log-body">
        <div v-if="!visibleLogs.length" class="log-empty">
          <el-icon class="log-empty-icon"><Document /></el-icon>
          <div class="log-empty-text">
            {{ logs.length ? '没有匹配的日志' : '暂无日志记录' }}
          </div>
          <div class="log-empty-sub">
            {{ logs.length ? '换个关键字，或点「全部」看所有级别' : '打开任意页面，这里就会记下接口与异常' }}
          </div>
        </div>

        <div v-else class="log-list">
          <div
            v-for="item in visibleLogs"
            :key="item.id"
            :class="['log-row', `is-${item.level}`]"
          >
            <span class="log-time">{{ item.time }}</span>
            <span class="log-level">{{ LEVEL_LABELS[item.level] }}</span>
            <span class="log-source">{{ SOURCE_LABELS[item.source] }}</span>
            <span class="log-msg">
              <span class="log-msg-main">{{ item.message }}</span>
              <span v-if="item.detail" class="log-msg-detail">{{ item.detail }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- —— 页脚 —— -->
      <footer class="log-foot">
        <span class="log-stat">
          共 <span class="num">{{ logs.length }}</span> 条
          <template v-if="errorCount">
            · 错误 <span class="num tone-seal">{{ errorCount }}</span>
          </template>
        </span>
        <span class="log-stat log-stat-sub">
          最多保留 {{ MAX_LOGS }} 条 · 仅记录前端可见信息
        </span>
      </footer>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { Close, Document, Search, Tickets } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  LEVEL_LABELS,
  LOG_LEVELS,
  MAX_LOGS,
  SOURCE_LABELS,
  getLogs,
  subscribeLogs,
  clearLogs,
  type LogEntry,
  type LogLevel,
} from '@/utils/logger'

const visible = defineModel<boolean>({ default: false })

/** 全部日志，最新的在最上面 */
const logs = ref<LogEntry[]>(getLogs())

/** 勾选了哪些级别；空集合 = 全部显示 */
const activeLevels = ref<Set<LogLevel>>(new Set())

/** 关键字 */
const keyword = ref('')

let unsubscribe: (() => void) | null = null

onMounted(() => {
  unsubscribe = subscribeLogs((next) => {
    logs.value = next
  })
})

onBeforeUnmount(() => {
  unsubscribe?.()
  unsubscribe = null
})

/** 切换某个级别的显示 */
const toggleLevel = (level: LogLevel) => {
  const next = new Set(activeLevels.value)
  if (next.has(level)) next.delete(level)
  else next.add(level)
  activeLevels.value = next
}

/** 某级别的条数 */
const countOf = (level: LogLevel) => logs.value.filter((item) => item.level === level).length

/** 错误条数（顶栏角标用） */
const errorCount = computed(() => countOf('error'))

/** 过滤后的日志 */
const visibleLogs = computed(() => {
  const levels = activeLevels.value
  const kw = keyword.value.trim().toLowerCase()
  return logs.value.filter((item) => {
    if (levels.size && !levels.has(item.level)) return false
    if (!kw) return true
    return (
      item.message.toLowerCase().includes(kw) ||
      (item.detail ?? '').toLowerCase().includes(kw) ||
      item.time.includes(kw)
    )
  })
})

/** 关闭 */
const close = () => {
  visible.value = false
}

/** 清空 */
const handleClear = () => {
  clearLogs()
}

/** 复制当前筛选结果 */
const handleCopy = async () => {
  const text = visibleLogs.value
    .map(
      (item) =>
        `[${item.time}] ${LEVEL_LABELS[item.level]} ${SOURCE_LABELS[item.source]} ${item.message}` +
        (item.detail ? ` ${item.detail}` : ''),
    )
    .join('\n')
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文下 clipboard API 可能不可用，退回老办法
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}
</script>

<style scoped lang="scss">
.log-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background-color: var(--paper);
}

/* —— 抬头 —— */
.log-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 2px solid var(--ink-900);

  .log-head-lf {
    display: flex;
    align-items: center;
    gap: 11px;
    min-width: 0;
  }

  .log-seal {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 30px;
    height: 30px;
    font-size: 16px;
    color: #fff;
    background-color: var(--ink-800);
    border-radius: var(--radius);
  }

  .log-head-text {
    min-width: 0;
  }

  .log-title {
    font-family: var(--font-display);
    font-size: 18px;
    line-height: 1.3;
    color: var(--text-ink);
    letter-spacing: 1px;
  }

  .log-sub {
    margin-top: 2px;
    font-size: 11.5px;
    color: var(--text-mute);
  }

  .log-head-ri {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .log-close {
    margin-left: 4px;
    font-size: 16px;
    color: var(--text-sub);
    cursor: pointer;

    &:hover {
      color: var(--seal);
    }
  }
}

/* —— 过滤条 —— */
.log-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 12px;
  flex-shrink: 0;
  padding: 10px 18px;
  background-color: var(--wash);
  border-bottom: 1px solid var(--rule-soft);
}

.log-chips {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.log-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  font-size: 12px;
  color: var(--text-sub);
  cursor: pointer;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  transition:
    color 0.16s ease,
    border-color 0.16s ease,
    background-color 0.16s ease;

  .log-chip-n {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-mute);
  }

  &:hover {
    border-color: var(--ink-600);
  }

  &.is-on {
    color: #fff;
    background-color: var(--ink-800);
    border-color: var(--ink-800);

    .log-chip-n {
      color: rgb(255 255 255 / 70%);
    }
  }
}

/* —— 正文 —— */
.log-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.log-list {
  padding: 4px 0 10px;
}

.log-row {
  display: grid;
  grid-template-columns: 84px 40px 48px 1fr;
  align-items: baseline;
  gap: 0 10px;
  padding: 7px 18px 7px 15px;
  font-size: 12.5px;
  line-height: 1.55;
  border-left: 3px solid transparent;
  border-bottom: 1px solid var(--rule-soft);

  &:hover {
    background-color: var(--wash);
  }

  .log-time {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 11.5px;
    color: var(--text-mute);
  }

  .log-level {
    font-size: 11.5px;
    font-weight: 600;
    text-align: center;
    border-radius: 2px;
  }

  .log-source {
    font-size: 11px;
    color: var(--text-mute);
  }

  .log-msg {
    min-width: 0;
    word-break: break-all;
  }

  .log-msg-main {
    color: var(--text-ink);
  }

  .log-msg-detail {
    display: block;
    margin-top: 2px;
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--text-sub);
  }

  /* 级别配色：一色一义 */
  &.is-error {
    border-left-color: var(--seal);
    .log-level {
      color: var(--seal);
    }
  }
  &.is-warn {
    border-left-color: var(--ochre);
    .log-level {
      color: var(--ochre);
    }
  }
  &.is-http {
    border-left-color: var(--jade);
    .log-level {
      color: var(--jade);
    }
  }
  &.is-info {
    border-left-color: var(--indigo);
    .log-level {
      color: var(--indigo);
    }
  }
  &.is-debug {
    border-left-color: var(--rule-strong);
    .log-level {
      color: var(--text-mute);
    }
  }
}

.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 220px;
  padding: 40px 20px;
  text-align: center;

  .log-empty-icon {
    font-size: 30px;
    color: var(--rule-strong);
  }

  .log-empty-text {
    margin-top: 12px;
    font-family: var(--font-display);
    font-size: 15px;
    color: var(--text-sub);
    letter-spacing: 0.5px;
  }

  .log-empty-sub {
    margin-top: 5px;
    font-size: 12px;
    color: var(--text-mute);
  }
}

/* —— 页脚 —— */
.log-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 12px;
  flex-shrink: 0;
  padding: 10px 18px;
  font-size: 11.5px;
  color: var(--text-sub);
  background-color: var(--wash);
  border-top: 1px solid var(--rule-soft);

  .log-stat-sub {
    color: var(--text-mute);
  }
}

/* 抽屉本体：去掉默认内边距，让面板铺满 */
:deep(.log-drawer .el-drawer__body) {
  padding: 0;
  overflow: hidden;
}

/* —— 窄屏：时间列让位给正文 —— */
@media (max-width: 560px) {
  .log-head {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .log-head-ri {
    justify-content: flex-end;
  }

  .log-row {
    grid-template-columns: 64px 36px 1fr;
    gap: 0 8px;
    padding: 7px 14px 7px 12px;

    .log-source {
      display: none;
    }
  }

  .log-head,
  .log-bar,
  .log-foot {
    padding-right: 14px;
    padding-left: 14px;
  }
}
</style>
