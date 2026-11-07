/**
 * =====================================================================
 * 知识库小助手 —— 前端 API 客户端
 * ---------------------------------------------------------------------
 * 【为什么不用 api/http.ts 那套】
 *   http.ts 走的是 Axios + 响应拦截器，拿到的是「一次性完整响应」。
 *   小助手要的是【流式】回答：模型边生成边吐字，前端边收边渲染，
 *   否则用户要盯着转圈等好几秒才看到第一句话。
 *   Axios 在浏览器里拿不到可读的流，所以这里用原生 fetch + ReadableStream。
 *
 * 【走哪个地址】
 *   开发环境：/kb -> Vite 代理 -> http://127.0.0.1:8010（kb_assistant 服务）
 *   生产环境：/kb -> Nginx 反代到小助手服务
 *   两种情况下浏览器都只跟同源打交道，不会触发 CORS。
 * =====================================================================
 */

/** 小助手服务的前缀 */
const KB_BASE = import.meta.env.VITE_KB_BASE || '/kb'

/** 服务端推过来的事件类型 */
export type KbEventType =
  | 'status'
  | 'sql'
  | 'token'
  | 'reset'
  | 'result'
  | 'done'
  | 'error'

/** 一条流式事件 */
export interface KbEvent {
  type: KbEventType
  data: Record<string, unknown>
}

/** 提问参数 */
export interface KbAskParams {
  question: string
  sessionId?: string | null
}

/** 查询结果 */
export interface KbQueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  elapsed_ms: number
  truncated: boolean
}

/** 非流式问答的返回 */
export interface KbAnswer {
  session_id: string
  answer: string
  sql: string | null
  result: KbQueryResult | null
  used_sql: boolean
  refused: boolean
}

/**
 * 把一段 SSE 文本拆成 { event, data } 对。
 * 一帧的格式是：
 *   event: token
 *   data: {"text":"你"}
 * 帧与帧之间用空行分隔。
 */
function parseFrame(frame: string): { type: KbEventType; data: Record<string, unknown> } | null {
  let type = 'message'
  const dataLines: string[] = []

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      type = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (!dataLines.length) return null

  const raw = dataLines.join('\n')
  try {
    return { type: type as KbEventType, data: JSON.parse(raw) }
  } catch {
    // 服务端偶尔会吐非 JSON（比如裸文本），原样交给上层
    return { type: type as KbEventType, data: { text: raw } }
  }
}

/**
 * 提问并逐条接收流式事件。
 *
 * @param params 问题和会话 id
 * @param onEvent 每收到一个事件就回调一次
 * @param signal  外部取消信号（组件卸载时用来断开连接）
 */
export async function askStream(
  params: KbAskParams,
  onEvent: (event: KbEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${KB_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: params.question,
      session_id: params.sessionId ?? null,
    }),
    signal,
  })

  if (!response.ok || !response.body) {
    // 读错误体，尽量给出后端给出的中文原因
    let message = `小管家服务响应异常（HTTP ${response.status}）`
    try {
      const body = await response.json()
      if (body?.message) message = String(body.message)
    } catch {
      /* 错误体不是 JSON，用默认文案 */
    }
    onEvent({ type: 'error', data: { message } })
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 按空行切帧
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const parsed = parseFrame(frame)
      if (parsed) onEvent(parsed)
      boundary = buffer.indexOf('\n\n')
    }
  }

  // 收尾：处理最后没有换行符的那一帧
  if (buffer.trim()) {
    const parsed = parseFrame(buffer)
    if (parsed) onEvent(parsed)
  }
}

/**
 * 提问并等待完整答案（非流式）。
 * 调试和自动化测试用这个更省事。
 */
export async function askOnce(params: KbAskParams): Promise<KbAnswer> {
  const response = await fetch(`${KB_BASE}/chat/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: params.question,
      session_id: params.sessionId ?? null,
    }),
  })

  if (!response.ok) {
    throw new Error(`小管家服务响应异常（HTTP ${response.status}）`)
  }

  return (await response.json()) as KbAnswer
}

/** 清空某个会话的上下文 */
export async function clearSession(sessionId: string): Promise<boolean> {
  const response = await fetch(`${KB_BASE}/session/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
  if (!response.ok) return false
  const body = await response.json()
  return Boolean(body?.ok)
}

/**
 * 健康检查。
 *
 * 注意：服务在「配置不全」时会返回 503（status = degraded），
 * 但响应体里带着有用的信息（缺哪一项配置）。
 * 所以这里【不能】因为 !response.ok 就返回 null ——
 * 否则前端会把「配置不全」误判成「服务没启动」。
 */
export async function checkHealth(): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(`${KB_BASE.replace(/\/$/, '')}/health`, {
      method: 'GET',
    })
    // 无论 200 还是 503，都把响应体解出来
    const body = await response.json()
    if (body && typeof body === 'object') {
      return body as Record<string, unknown>
    }
    return null
  } catch {
    // 请求根本发不出去 —— 服务没启动
    return null
  }
}
