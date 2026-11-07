/**
 * =====================================================================
 * 颜色工具
 * ---------------------------------------------------------------------
 * 移植自 Geeker-Admin（MIT License, Copyright (c) 2022 Halsey）。
 * 用途：由一个主色自动推导 Element Plus 需要的整套色阶，
 *       这样改一次主色，整站按钮 / 标签 / 菜单 / 图表都会跟着变。
 * =====================================================================
 */

/** hex 颜色 -> [r, g, b] */
export function hexToRgb(str: string): number[] {
  const reg = /^#?[0-9A-Fa-f]{6}$/
  if (!reg.test(str)) {
    throw new Error(`颜色格式不正确：${str}`)
  }
  const hexs = str.replace('#', '').match(/../g)!
  return hexs.map((h) => parseInt(h, 16))
}

/** [r, g, b] -> hex 颜色 */
export function rgbToHex(r: number, g: number, b: number): string {
  const hexs = [r.toString(16), g.toString(16), b.toString(16)].map((h) =>
    h.length === 1 ? `0${h}` : h,
  )
  return `#${hexs.join('')}`
}

/**
 * 加深颜色（level: 0 ~ 1，越大越黑）
 * Element Plus 的 --el-color-primary-dark-2 用这个。
 */
export function getDarkColor(color: string, level: number): string {
  const rgb = hexToRgb(color)
  const mixed = rgb.map((c) => Math.round(20.5 * level + c * (1 - level)))
  return rgbToHex(mixed[0], mixed[1], mixed[2])
}

/**
 * 变浅颜色（level: 0 ~ 1，越大越接近白）
 * Element Plus 的 --el-color-primary-light-3/5/7/8/9 用这个。
 */
export function getLightColor(color: string, level: number): string {
  const rgb = hexToRgb(color)
  const mixed = rgb.map((c) => Math.round(255 * level + c * (1 - level)))
  return rgbToHex(mixed[0], mixed[1], mixed[2])
}

/**
 * 把主色写进 CSS 变量，Element Plus 组件立即生效。
 */
export function applyPrimaryColor(primary: string) {
  const root = document.documentElement.style
  root.setProperty('--el-color-primary', primary)
  for (let i = 1; i <= 9; i++) {
    root.setProperty(`--el-color-primary-light-${i}`, getLightColor(primary, i / 10))
  }
  root.setProperty('--el-color-primary-dark-2', getDarkColor(primary, 0.2))
}
