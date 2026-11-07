<!--
  =====================================================================
  知识库小管家 —— 悬浮球 + 聊天抽屉
  ---------------------------------------------------------------------
  【挂载位置】
    layouts/BasicLayout.vue —— 也就是路由守卫之后的主框架。
    未登录访问任何受保护页面都会被守卫踢回登录页，
    所以小管家【天然只在登录后才出现】，不需要额外判断登录态。

  【能做什么】
    · 问业务数据：学员、班级、成绩、就业 → 小管家自己转 SQL 查库
    · 问系统用法：模块、接口、表结构 → 小管家从知识库回答
    · 问跑题内容 → 小管家会礼貌地拒绝（见 kb_assistant/app/scope.py）

  【交互】
    点右下角的小管家 → 打开聊天抽屉 → 输入问题 → 流式看回答。
  =====================================================================
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Close, Delete, Promotion, Loading } from '@element-plus/icons-vue'

import { askStream, checkHealth, clearSession, type KbEvent } from '@/api/kb'
import { renderMarkdown } from '@/utils/markdown'
import avatarUrl from '@/assets/kb-assistant.png'

/** 助手的一条消息 */
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** 本轮执行的 SQL（助手消息才有） */
  sql?: string
  /** 本轮查询结果 */
  result?: {
    columns: string[]
    rows: Record<string, unknown>[]
    row_count: number
    elapsed_ms: number
    truncated: boolean
  }
  /** 出错信息 */
  error?: string
  /** 是否还在流式接收中 */
  streaming?: boolean
}

const open = ref(false)
const input = ref('')
const loading = ref(false)
/** 当前阶段提示（正在理解问题 / 正在查库 / 正在组织回答…） */
const phase = ref('')
const messages = ref<ChatMessage[]>([])
const sessionId = ref<string | null>(null)
/**
 * 服务状态：
 *   'up'       —— 服务正常，配置齐全
 *   'degraded' —— 服务在跑，但配置不全（比如 .env 里没填 MINIMAX_API_KEY）
 *   'down'     —— 连都连不上（服务没启动）
 */
const serviceState = ref<'up' | 'degraded' | 'down'>('down')
/** 配置缺了什么（degraded 时告诉用户缺哪一项） */
const missingConfig = ref<string[]>([])
/** 首次出现时的招呼卡片 */
const greeting = ref(false)
/** 展开「本次查询」的哪一块 */
const detailOpen = ref<Record<number, boolean>>({})

const listRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
let controller: AbortController | null = null

/** 招呼语 */
const GREETING_TEXT = '你好呀～我是小管家，这个系统的数据我都能帮你查。'

/** 空态里的示例问题 */
const SAMPLE_TIPS = [
  '这个系统有哪些功能模块？',
  '1 号班一共有多少学生？',
  '就业薪资最高的 5 个学生是谁？',
  '数据库里有哪些表？',
]

/** 服务不可用时的提示 */
const SERVICE_HINT = '小管家服务没连上，请先启动 kb_assistant 服务'

/** 顶栏副标题：把「服务现在什么状态」讲清楚 */
const statusText = computed(() => {
  if (serviceState.value === 'up') return '教务知识管家 · 基于本系统数据'
  if (serviceState.value === 'degraded') {
    return `还差 ${missingConfig.value.join('、')}，请在 .env 里补上`
  }
  return SERVICE_HINT
})

const canSend = computed(() => input.value.trim().length > 0 && !loading.value)

/** 渲染后的消息 HTML（模型输出先转义再拼标签） */
function messageHtml(content: string): string {
  return renderMarkdown(content)
}

/** 滚到底部 */
async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

/** 打开抽屉 */
async function togglePanel() {
  open.value = !open.value
  if (open.value) {
    greeting.value = false
    await nextTick()
    inputRef.value?.focus()
  }
}

/** 收起招呼气泡 */
function dismissGreeting() {
  greeting.value = false
}

/** 发送问题 */
async function send() {
  const question = input.value.trim()
  if (!question || loading.value) return

  // 服务不可用时，在这里才提示 —— 用户正要发消息了，
  // 这时候告诉他「还差什么」才有意义，而不是每次进页面就吵一遍。
  if (serviceState.value !== 'up') {
    ElMessage.warning(
      serviceState.value === 'degraded'
        ? `小管家配置不完整：${missingConfig.value.join('、')}，请在 .env 里补上`
        : SERVICE_HINT
    )
    return
  }

  input.value = ''
  loading.value = true
  phase.value = '正在思考…'

  // 用户消息 + 一个空的助手消息（流式往里填）
  messages.value.push({ role: 'user', content: question })
  const reply: ChatMessage = { role: 'assistant', content: '', streaming: true }
  messages.value.push(reply)
  await scrollToBottom()

  controller = new AbortController()

  const handleEvent = (event: KbEvent) => {
    switch (event.type) {
      case 'status':
        phase.value = String(event.data.text ?? '')
        break

      case 'sql':
        reply.sql = String(event.data.sql ?? '')
        break

      case 'token':
        reply.content += String(event.data.text ?? '')
        scrollToBottom()
        break

      case 'reset':
        // 模型越界被服务端拦下，整段回答换成拒答话术
        reply.content = String(event.data.text ?? '')
        break

      case 'result':
        reply.result = event.data as ChatMessage['result']
        break

      case 'error':
        reply.error = String(event.data.message ?? '小管家出了点问题')
        break

      case 'done':
        sessionId.value = String(event.data.session_id ?? '') || sessionId.value
        reply.streaming = false
        phase.value = ''
        loading.value = false
        break
    }
  }

  try {
    await askStream({ question, sessionId: sessionId.value }, handleEvent, controller.signal)
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') {
      // 用户主动取消，不是错误
    } else {
      reply.error = error instanceof Error ? error.message : '连接小管家失败'
      ElMessage.error(reply.error)
    }
  } finally {
    reply.streaming = false
    loading.value = false
    phase.value = ''
    controller = null
    scrollToBottom()
  }
}

/** 停止生成 */
function stop() {
  controller?.abort()
  controller = null
  loading.value = false
  phase.value = ''
}

/** 清空当前会话 */
async function resetChat() {
  const current = sessionId.value
  if (current) {
    try {
      await clearSession(current)
    } catch {
      /* 清空失败不影响本地重置 */
    }
  }
  messages.value = []
  sessionId.value = null
  phase.value = ''
  loading.value = false
  ElMessage.success('已清空对话')
}

/** 展开/收起「本次查询」详情 */
function toggleDetail(index: number) {
  detailOpen.value[index] = !detailOpen.value[index]
}

/** 回车发送、Shift+回车换行 */
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

/** 服务健康检查 */
async function probe() {
  const health = await checkHealth()
  if (!health) {
    // 连不上 —— 服务没启动
    serviceState.value = 'down'
    return
  }

  missingConfig.value = (health.missing_config as string[] | undefined) ?? []
  // degraded 表示「服务在跑，但配置不齐」，和「服务没启动」要区分开
  serviceState.value = health.status === 'ok' ? 'up' : 'degraded'
  // 这里不弹 toast：状态已经由悬浮球角标（!）、球上的 title 提示、
  // 面板副标题三处表达清楚了。挂载就弹一次全局提示，等于每次翻页都打扰用户，
  // 还会糊在页面顶上（截图里尤其显眼）。
  // 真正需要提醒的是「用户正要发消息却用不了」的那一刻 —— 见 send()。
}

watch(open, (val) => {
  if (val) {
    scrollToBottom()
  }
})

onMounted(async () => {
  await probe()
  // 服务就绪后打个招呼，让用户知道小管家在
  if (serviceState.value === 'up') {
    greeting.value = true
    setTimeout(() => {
      greeting.value = false
    }, 6000)
  }
})

onBeforeUnmount(() => {
  controller?.abort()
})
</script>

<template>
  <!-- 悬浮球 + 抽屉 -->
  <div class="kb-assistant">
    <!-- 招呼卡片：头像 + 名号 + 一句话 -->
    <transition name="kb-fade">
      <div v-if="greeting && !open" class="kb-greeting" @click="dismissGreeting">
        <img class="kb-greeting-avatar" :src="avatarUrl" alt="小管家" />
        <div class="kb-greeting-body">
          <p class="kb-greeting-title">小管家</p>
          <p class="kb-greeting-text">{{ GREETING_TEXT }}</p>
        </div>
      </div>
    </transition>

    <!-- 悬浮球 -->
    <button
      class="kb-orb"
      :class="{ 'is-open': open, 'is-off': serviceState === 'down' }"
      type="button"
      :title="statusText"
      @click="togglePanel"
    >
      <img class="kb-orb-img" :src="avatarUrl" alt="小管家" />
      <span v-if="serviceState === 'degraded'" class="kb-orb-badge is-error">!</span>
      <span v-else-if="serviceState === 'down'" class="kb-orb-badge is-error">!</span>
      <span v-else-if="!open" class="kb-orb-badge"></span>
      <span v-if="loading" class="kb-orb-loading">
        <el-icon><Loading /></el-icon>
      </span>
    </button>

    <!-- 聊天抽屉 -->
    <transition name="kb-slide">
      <section v-if="open" class="kb-panel">
        <!-- 抬头 -->
        <header class="kb-head">
          <img class="kb-head-avatar" :src="avatarUrl" alt="小管家" />
          <div class="kb-head-info">
            <h3 class="kb-head-title">小管家</h3>
            <p class="kb-head-sub">
              {{ statusText }}
            </p>
          </div>
          <div class="kb-head-actions">
            <el-tooltip content="清空对话" placement="bottom">
              <el-button text size="small" @click="resetChat">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="收起" placement="bottom">
              <el-button text size="small" @click="togglePanel">
                <el-icon><Close /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </header>

        <!-- 消息区 -->
        <div ref="listRef" class="kb-list">
          <!-- 空态：给出几个示例问题 -->
          <div v-if="!messages.length" class="kb-empty">
            <img class="kb-empty-avatar" :src="avatarUrl" alt="小管家" />
            <p class="kb-empty-title">有什么想了解的，尽管问我～</p>
            <ul class="kb-samples">
              <li v-for="tip in SAMPLE_TIPS" :key="tip" @click="input = tip; send()">
                {{ tip }}
              </li>
            </ul>
          </div>

          <!-- 消息 -->
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="kb-msg"
            :class="msg.role === 'user' ? 'is-user' : 'is-assistant'"
          >
            <img v-if="msg.role === 'assistant'" class="kb-msg-avatar" :src="avatarUrl" alt="" />

            <div class="kb-msg-body">
              <!-- 助手消息 -->
              <template v-if="msg.role === 'assistant'">
                <div v-if="msg.error" class="kb-error">{{ msg.error }}</div>

                <div
                  v-else-if="msg.content"
                  class="kb-bubble kb-bubble-assistant"
                  v-html="messageHtml(msg.content)"
                ></div>

                <div v-else-if="msg.streaming" class="kb-bubble kb-bubble-assistant">
                  <span class="kb-typing"><i></i><i></i><i></i></span>
                </div>

                <!-- 本次查询的详情 -->
                <div v-if="msg.sql || msg.result" class="kb-detail">
                  <button class="kb-detail-toggle" @click="toggleDetail(index)">
                    <el-icon><ChatDotRound /></el-icon>
                    <span>本次查询</span>
                    <em v-if="msg.result" class="kb-detail-meta num">
                      {{ msg.result.row_count }} 行 · {{ msg.result.elapsed_ms }}ms
                    </em>
                  </button>

                  <div v-if="detailOpen[index]" class="kb-detail-body">
                    <pre v-if="msg.sql" class="kb-sql">{{ msg.sql }}</pre>

                    <div v-if="msg.result?.rows?.length" class="kb-table-wrap">
                      <table class="kb-table">
                        <thead>
                          <tr>
                            <th v-for="col in msg.result.columns" :key="col">{{ col }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(row, r) in msg.result.rows.slice(0, 20)" :key="r">
                            <td v-for="col in msg.result.columns" :key="col" class="num">
                              {{ row[col] ?? '—' }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      <p v-if="msg.result.rows.length > 20" class="kb-table-more">
                        仅显示前 20 行，共 {{ msg.result.row_count }} 行
                      </p>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 用户消息 -->
              <div v-else class="kb-bubble kb-bubble-user">{{ msg.content }}</div>
            </div>
          </div>
        </div>

        <!-- 阶段提示 -->
        <div v-if="phase" class="kb-phase">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ phase }}</span>
        </div>

        <!-- 输入区 -->
        <footer class="kb-foot">
          <el-input
            ref="inputRef"
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            maxlength="500"
            placeholder="想问什么？比如「1 号班有多少学生」"
            @keydown="onKeydown"
          />
          <div class="kb-foot-actions">
            <span class="kb-hint">Enter 发送 · Shift+Enter 换行</span>
            <el-button v-if="loading" size="small" @click="stop">停止</el-button>
            <el-button
              v-else
              type="primary"
              size="small"
              :disabled="!canSend"
              @click="send"
            >
              <el-icon><Promotion /></el-icon>
              <span>发送</span>
            </el-button>
          </div>
        </footer>
      </section>
    </transition>
  </div>
</template>

<style scoped>
/* ---------------------------------------------------------------------
 * 悬浮球
 * ------------------------------------------------------------------ */
.kb-assistant {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
}

.kb-orb {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  padding: 0;
  cursor: pointer;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 50%;
  box-shadow: 0 4px 16px rgb(22 33 45 / 16%);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--ink-600);
    box-shadow: 0 6px 20px rgb(22 33 45 / 22%);
  }

  &.is-open {
    border-color: var(--ink-900);
  }

  /* 服务没起来：灰掉并标红 */
  &.is-off {
    filter: grayscale(0.85);
    opacity: 0.75;
  }
}

.kb-orb-img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 50%;
}

/* 未读提示点 */
.kb-orb-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 11px;
  height: 11px;
  background-color: var(--seal);
  border: 2px solid var(--paper);
  border-radius: 50%;

  &.is-error {
    top: 4px;
    right: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 700;
    color: #fff;
  }
}

/* 生成中的转圈 */
.kb-orb-loading {
  position: absolute;
  right: -2px;
  bottom: -2px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  font-size: 13px;
  color: #fff;
  background-color: var(--ink-700);
  border: 2px solid var(--paper);
  border-radius: 50%;
}

/* ---------------------------------------------------------------------
 * 招呼卡片
 *   竖签：原来是横着的一条便笺（230 宽 × 约 90 高），
 *   按要求把长宽对调 —— 现在是 148 宽 × 230 高的一张竖条，
 *   像案头递上来的一张窄签：头像在上、名号居中、一句话在下面。
 * ------------------------------------------------------------------ */
.kb-greeting {
  position: absolute;
  right: 76px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  box-sizing: border-box;
  width: 148px;
  height: 230px;
  max-width: calc(100vw - 110px);
  padding: 14px 12px;
  text-align: center;
  cursor: pointer;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-top: 2px solid var(--seal);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 14px rgb(22 33 45 / 12%);

  /* 指向悬浮球的小角 */
  &::after {
    position: absolute;
    right: -6px;
    bottom: 18px;
    width: 10px;
    height: 10px;
    content: '';
    background-color: var(--paper);
    border-top: 1px solid var(--rule);
    border-right: 1px solid var(--rule);
    transform: rotate(45deg);
  }
}

/* 卡片头像：小一圈，像签名的落款 */
.kb-greeting-avatar {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  object-fit: cover;
  background-color: var(--wash);
  border: 1px solid var(--rule);
  border-radius: 50%;
}

.kb-greeting-body {
  width: 100%;
  min-width: 0;
}

/* 名号：楷体，像文书抬头 */
.kb-greeting-title {
  margin: 0 0 3px;
  font-family: var(--font-display);
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text-ink);
  letter-spacing: 1px;
}

/* 正文：一句话，短句换行，不折断词 */
.kb-greeting-text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text);
  overflow-wrap: break-word;
}

/* ---------------------------------------------------------------------
 * 聊天抽屉
 * ------------------------------------------------------------------ */
.kb-panel {
  position: absolute;
  right: 0;
  bottom: 78px;
  display: flex;
  flex-direction: column;
  /* 聊天抽屉保持竖长：对话多的时候往下读比往右读顺手 */
  width: 408px;
  height: 560px;
  max-width: calc(100vw - 40px);
  overflow: hidden;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-top: 2px solid var(--ink-900);
  border-radius: var(--radius-lg);
  box-shadow: 0 10px 34px rgb(22 33 45 / 18%);
}

/* 抬头 */
.kb-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  padding: 12px 14px;
  background-color: var(--wash);
  border-bottom: 1px solid var(--rule);
}

.kb-head-avatar {
  width: 36px;
  height: 36px;
  object-fit: cover;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 50%;
}

.kb-head-info {
  flex: 1;
  min-width: 0;
}

.kb-head-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 400;
  line-height: 1.2;
  color: var(--text-ink);
  letter-spacing: 2px;
}

.kb-head-sub {
  margin: 2px 0 0;
  overflow: hidden;
  font-size: 11.5px;
  color: var(--text-sub);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-head-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

/* 消息区 */
.kb-list {
  flex: 1;
  padding: 14px;
  overflow-y: auto;
  background-color: var(--canvas);
}

/* 空态 */
.kb-empty {
  padding: 22px 8px;
  text-align: center;
}

.kb-empty-avatar {
  width: 72px;
  height: 72px;
  object-fit: cover;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 50%;
}

.kb-empty-title {
  margin: 10px 0 12px;
  font-size: 13px;
  color: var(--text-sub);
}

.kb-samples {
  padding: 0;
  margin: 0;
  list-style: none;

  li {
    padding: 7px 11px;
    margin-bottom: 7px;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--text);
    text-align: left;
    cursor: pointer;
    background-color: var(--paper);
    border: 1px solid var(--rule-soft);
    border-radius: var(--radius);

    &:hover {
      color: var(--indigo);
      border-color: var(--indigo);
    }
  }
}

/* 单条消息 */
.kb-msg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;

  &.is-user {
    justify-content: flex-end;
  }
}

.kb-msg-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  object-fit: cover;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 50%;
}

.kb-msg-body {
  min-width: 0;
  max-width: 84%;
}

/* 气泡 */
.kb-bubble {
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.72;
  word-break: break-word;
  border-radius: var(--radius-lg);
}

.kb-bubble-user {
  color: #fff;
  background-color: var(--ink-700);
  border-top-right-radius: 0;
}

.kb-bubble-assistant {
  color: var(--text);
  background-color: var(--paper);
  border: 1px solid var(--rule-soft);
  border-top-left-radius: 0;
}

.kb-error {
  padding: 9px 12px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--seal);
  background-color: var(--seal-soft);
  border: 1px solid #f0d3ce;
  border-radius: var(--radius-lg);
}

/* ---------------------------------------------------------------------
 * 「本次查询」详情
 * ------------------------------------------------------------------ */
.kb-detail {
  margin-top: 6px;
}

.kb-detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  font-size: 11.5px;
  color: var(--text-sub);
  cursor: pointer;
  background-color: var(--wash);
  border: 1px solid var(--rule-soft);
  border-radius: 2px;

  &:hover {
    color: var(--indigo);
    border-color: var(--rule-strong);
  }
}

.kb-detail-meta {
  color: var(--text-mute);
}

.kb-detail-body {
  padding: 8px;
  margin-top: 6px;
  background-color: var(--paper);
  border: 1px solid var(--rule-soft);
  border-radius: var(--radius);
}

.kb-sql {
  padding: 8px 10px;
  margin: 0 0 8px;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-ink);
  background-color: var(--wash);
  border-radius: 2px;
}

.kb-table-wrap {
  max-height: 210px;
  overflow: auto;
}

.kb-table {
  width: 100%;
  font-size: 11.5px;
  border-collapse: collapse;

  th,
  td {
    padding: 4px 7px;
    text-align: left;
    white-space: nowrap;
    border-bottom: 1px solid var(--rule-soft);
  }

  th {
    position: sticky;
    top: 0;
    font-weight: 600;
    color: var(--text-sub);
    background-color: var(--wash);
  }

  td {
    font-family: var(--font-mono);
    color: var(--text);
  }
}

.kb-table-more {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--text-mute);
}

/* ---------------------------------------------------------------------
 * 阶段提示
 * ------------------------------------------------------------------ */
.kb-phase {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 11.5px;
  color: var(--text-sub);
  background-color: var(--wash);
  border-top: 1px solid var(--rule-soft);
}

/* ---------------------------------------------------------------------
 * 输入区
 * ------------------------------------------------------------------ */
.kb-foot {
  flex-shrink: 0;
  padding: 10px 12px 12px;
  background-color: var(--paper);
  border-top: 1px solid var(--rule);
}

.kb-foot-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
}

.kb-hint {
  font-size: 11px;
  color: var(--text-mute);
}

/* ---------------------------------------------------------------------
 * 打字机动画
 * ------------------------------------------------------------------ */
.kb-typing {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  height: 18px;

  i {
    width: 5px;
    height: 5px;
    background-color: var(--text-mute);
    border-radius: 50%;
    animation: kb-blink 1.3s infinite ease-in-out;

    &:nth-child(2) {
      animation-delay: 0.18s;
    }

    &:nth-child(3) {
      animation-delay: 0.36s;
    }
  }
}

@keyframes kb-blink {
  0%,
  60%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

/* ---------------------------------------------------------------------
 * 过渡
 * ------------------------------------------------------------------ */
.kb-fade-enter-active,
.kb-fade-leave-active {
  transition: opacity 0.25s ease;
}

.kb-fade-enter-from,
.kb-fade-leave-to {
  opacity: 0;
}

.kb-slide-enter-active,
.kb-slide-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.kb-slide-enter-from,
.kb-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

/* ---------------------------------------------------------------------
 * 窄屏
 * ------------------------------------------------------------------ */
@media (max-width: 520px) {
  .kb-assistant {
    right: 14px;
    bottom: 14px;
  }

  .kb-panel {
    position: fixed;
    right: 8px;
    bottom: 8px;
    left: 8px;
    width: auto;
    height: calc(100vh - 16px);
  }

  .kb-greeting {
    right: 70px;
  }
}
</style>

<style>
/**
 * 助手消息里的 Markdown 样式。
 * 这些内容是 v-html 进来的，作用域样式（scoped）管不到，
 * 所以单独开一段非 scoped 的样式，用 .kb-bubble-assistant 限定作用域。
 */
.kb-bubble-assistant .md-p {
  margin: 0 0 6px;

  &:last-child {
    margin-bottom: 0;
  }
}

.kb-bubble-assistant .md-h {
  margin: 8px 0 4px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-ink);
}

.kb-bubble-assistant .md-list {
  padding-left: 18px;
  margin: 4px 0 6px;
}

.kb-bubble-assistant .md-list li {
  margin-bottom: 2px;
}

.kb-bubble-assistant strong {
  font-weight: 600;
  color: var(--text-ink);
}

.kb-bubble-assistant code {
  padding: 1px 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--indigo);
  background-color: var(--indigo-soft);
  border-radius: 2px;
}

.kb-bubble-assistant .md-pre {
  padding: 9px 11px;
  margin: 6px 0;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-ink);
  background-color: var(--wash);
  border: 1px solid var(--rule-soft);
  border-radius: 2px;
}

.kb-bubble-assistant .md-pre code {
  padding: 0;
  font-size: inherit;
  color: inherit;
  background: none;
}

.kb-bubble-assistant .md-table {
  width: 100%;
  margin: 6px 0;
  font-size: 12px;
  border-collapse: collapse;
}

.kb-bubble-assistant .md-table th,
.kb-bubble-assistant .md-table td {
  padding: 4px 8px;
  text-align: left;
  border-bottom: 1px solid var(--rule-soft);
}

.kb-bubble-assistant .md-table th {
  font-weight: 600;
  color: var(--text-sub);
  background-color: var(--wash);
}

.kb-bubble-assistant .md-quote {
  padding-left: 9px;
  margin: 5px 0;
  color: var(--text-sub);
  border-left: 2px solid var(--rule-strong);
}

.kb-bubble-assistant .md-hr {
  margin: 8px 0;
  border: none;
  border-top: 1px solid var(--rule-soft);
}
</style>
