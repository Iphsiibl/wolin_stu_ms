/**
 * =====================================================================
 * 极简 Markdown 渲染器
 * ---------------------------------------------------------------------
 * 【为什么自己写而不装 marked / markdown-it】
 *   1. 少一个依赖 —— 这个项目前端依赖已经很满了；
 *   2. 小助手的回答格式是【受控的】：标题、加粗、列表、表格、行内代码、
 *      少量段落。自己写一个刚好够用的，行为可预期；
 *   3. 必须先转义再拼 HTML —— 模型输出是不可信输入，
 *      直接 v-html 会变成 XSS 入口。这里每一步都转义。
 *
 * 【支持】
 *   # ~ ######  标题
 *   **粗体**、*斜体*、`行内代码`
 *   - / * / +  无序列表
 *   1. 2. 3.   有序列表
 *   | a | b |  表格（带表头分隔行）
 *   > 引用
 *   ``` 代码块 ```
 *   ---  分隔线
 * =====================================================================
 */

/** HTML 转义 —— 所有模型输出在进 DOM 之前都要过这一遍 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 行内标记：粗体、斜体、行内代码 */
function renderInline(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
}

/**
 * 把 Markdown 文本渲染成 HTML。
 *
 * @param source 原始文本
 * @returns 可直接 v-html 的 HTML 字符串（内容已转义）
 */
export function renderMarkdown(source: string): string {
  if (!source) return ''

  const lines = escapeHtml(source).split('\n')
  const out: string[] = []

  let inCode = false
  let codeBuffer: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let tableBuffer: string[] = []

  /** 收尾一个列表 */
  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  /** 收尾一个表格 */
  const flushTable = () => {
    if (!tableBuffer.length) return

    const rows = tableBuffer
      .map((row) =>
        row
          .replace(/^\s*\|/, '')
          .replace(/\|\s*$/, '')
          .split('|')
          .map((cell) => cell.trim()),
      )
      // 表头分隔行（|---|---|）不渲染成单元格
      .filter((_, index) => index !== 1)

    if (!rows.length) {
      tableBuffer = []
      return
    }

    const [head, ...body] = rows
    out.push('<table class="md-table"><thead><tr>')
    head.forEach((cell) => out.push(`<th>${renderInline(cell)}</th>`))
    out.push('</tr></thead><tbody>')
    body.forEach((row) => {
      out.push('<tr>')
      row.forEach((cell) => out.push(`<td>${renderInline(cell)}</td>`))
      out.push('</tr>')
    })
    out.push('</tbody></table>')

    tableBuffer = []
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()

    // ---- 代码块 ----
    if (line.trim().startsWith('```')) {
      if (inCode) {
        out.push(`<pre class="md-pre"><code>${codeBuffer.join('\n')}</code></pre>`)
        codeBuffer = []
        inCode = false
      } else {
        closeList()
        flushTable()
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeBuffer.push(rawLine)
      continue
    }

    // ---- 表格行 ----
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      closeList()
      tableBuffer.push(line.trim())
      continue
    }
    flushTable()

    // ---- 空行 ----
    if (!line.trim()) {
      closeList()
      continue
    }

    // ---- 标题 ----
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      closeList()
      const level = Math.min(heading[1].length + 2, 6)
      out.push(`<h${level} class="md-h">${renderInline(heading[2])}</h${level}>`)
      continue
    }

    // ---- 分隔线 ----
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
      closeList()
      out.push('<hr class="md-hr">')
      continue
    }

    // ---- 引用 ----
    const quote = line.match(/^&gt;\s?(.*)$/)
    if (quote) {
      closeList()
      out.push(`<blockquote class="md-quote">${renderInline(quote[1])}</blockquote>`)
      continue
    }

    // ---- 列表 ----
    const unordered = line.match(/^\s*[-*+]\s+(.*)$/)
    const ordered = line.match(/^\s*(\d+)[.)]\s+(.*)$/)

    if (unordered || ordered) {
      const want = unordered ? 'ul' : 'ol'
      if (listType !== want) {
        closeList()
        out.push(`<${want} class="md-list">`)
        listType = want
      }
      const content = unordered ? unordered[1] : ordered![2]
      out.push(`<li>${renderInline(content)}</li>`)
      continue
    }

    // ---- 普通段落 ----
    closeList()
    out.push(`<p class="md-p">${renderInline(line)}</p>`)
  }

  // 收尾
  if (inCode && codeBuffer.length) {
    out.push(`<pre class="md-pre"><code>${codeBuffer.join('\n')}</code></pre>`)
  }
  flushTable()
  closeList()

  return out.join('')
}
