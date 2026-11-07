<!--
  =====================================================================
  品牌印章 BrandSeal —— 朱砂方印
  ---------------------------------------------------------------------
  一枚「钤」在纸上的朱砂方印：印面正中一个「管」字。

  【为什么不用图片】
    全部用 CSS + 内联 SVG 画出来：不引图片、不引新依赖，
    任何尺寸都清晰 —— 字号走 font-size，描边 / 圆角 / 字形全用 em，
    size 改一下，整枚印章同比缩放。

  【钤印质感从哪来】
    · 印色不匀 —— 印面叠两层径向渐变：边重心轻，右上留一块淡斑
    · 轻微噪点 —— 内联 SVG 的 feTurbulence 生成深色颗粒与飞白碎点
    · 边缘毛糙 —— feDisplacementMap 把方印的四边推得微微起伏

  【用法】
    <BrandSeal :size="40" />                 数字按 px 算
    <BrandSeal size="2.5rem" />              字符串按 CSS 长度原样用
    <BrandSeal :size="34" label="学管家印章" />

  【颜色】
    一律取自全局 token（--seal / --seal-deep / --seal-soft / --paper），
    组件内不写死任何色值。
  =====================================================================
-->
<script setup lang="ts">
import { computed, useId } from 'vue'

/**
 * 品牌印章
 *
 * @prop size  印章边长：数字按 px，字符串按 CSS 长度原样用
 * @prop label 替代文本（印章是图形，得有个可读的名字）
 */
const props = withDefaults(
  defineProps<{
    /** 印章边长：数字 = px，字符串 = CSS 长度 */
    size?: number | string
    /** 印章的替代文本 */
    label?: string
  }>(),
  {
    size: 40,
    label: '学管家印章',
  },
)

/** 边长统一成 CSS 长度：纯数字串也按 px 算 */
const sizeCss = computed(() => {
  const raw = props.size
  if (typeof raw === 'number') return `${raw}px`
  const text = String(raw).trim()
  if (!text) return '40px'
  return /^\d+(\.\d+)?$/.test(text) ? `${text}px` : text
})

/** 毛边幅度：跟着边长走，大印粗糙一点，小印克制一点 */
const roughScale = computed(() => {
  const px = parseFloat(String(props.size))
  const base = Number.isFinite(px) ? px : 40
  return Math.min(Math.max(base * 0.045, 0.8), 2.6)
})

/** SVG 滤镜 id 必须每份实例唯一，否则多个印章会互相串扰 */
const uid = useId()
const roughId = `brand-seal-rough-${uid}`
const grainId = `brand-seal-grain-${uid}`
const fleckId = `brand-seal-fleck-${uid}`
</script>

<template>
  <span class="brand-seal" :style="{ fontSize: sizeCss }" role="img" :aria-label="label">
    <!-- 印面：朱砂底 + 不匀的印色 + 颗粒 + 毛糙的边 -->
    <span class="brand-seal-plate" aria-hidden="true" :style="{ filter: `url(#${roughId})` }">
      <svg class="brand-seal-grain" focusable="false">
        <defs>
          <!-- 毛边：把方印的四边推得微微起伏，像手钤出来 -->
          <filter
            :id="roughId"
            x="-6%"
            y="-6%"
            width="112%"
            height="112%"
            color-interpolation-filters="sRGB"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.28"
              numOctaves="3"
              seed="3"
              result="edge"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="edge"
              :scale="roughScale"
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>

          <!-- 颗粒：细密的深色噪点，印色深浅不匀 -->
          <filter
            :id="grainId"
            x="0%"
            y="0%"
            width="100%"
            height="100%"
            color-interpolation-filters="sRGB"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.5"
              numOctaves="3"
              seed="9"
              result="noise"
            />
            <feColorMatrix
              in="noise"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 5 -2.5"
              result="noiseAlpha"
            />
            <feComposite in="SourceGraphic" in2="noiseAlpha" operator="in" />
          </filter>

          <!-- 飞白：没吃上墨的碎点 -->
          <filter
            :id="fleckId"
            x="0%"
            y="0%"
            width="100%"
            height="100%"
            color-interpolation-filters="sRGB"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.95"
              numOctaves="2"
              seed="21"
              result="fleck"
            />
            <feColorMatrix
              in="fleck"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 6 -3.6"
              result="fleckAlpha"
            />
            <feComposite in="SourceGraphic" in2="fleckAlpha" operator="in" />
          </filter>
        </defs>

        <rect
          class="brand-seal-grain-dark"
          x="0"
          y="0"
          width="100%"
          height="100%"
          :filter="`url(#${grainId})`"
        />
        <rect
          class="brand-seal-grain-light"
          x="0"
          y="0"
          width="100%"
          height="100%"
          :filter="`url(#${fleckId})`"
        />
      </svg>
    </span>

    <!-- 内白描边：一圈白线，像钤在纸上的印 -->
    <span class="brand-seal-ring" aria-hidden="true"></span>

    <!-- 印文 -->
    <span class="brand-seal-char" aria-hidden="true">管</span>
  </span>
</template>

<style scoped>
/* ---------------------------------------------------------------------
 * 印章本体
 *   尺寸挂在 font-size 上：内部所有分量都用 em，跟着 size 一起长。
 * ------------------------------------------------------------------ */
.brand-seal {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 1em;
  height: 1em;
  border-radius: 0.05em;
  user-select: none;
}

/* 印面：朱砂底，边重心轻，右上一块淡斑 */
.brand-seal-plate {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border-radius: 0.05em;
  background-color: var(--seal);
  background-image:
    radial-gradient(circle at 26% 22%, var(--seal-soft) 0%, transparent 46%),
    radial-gradient(circle at 50% 50%, transparent 22%, var(--seal-deep) 118%);
}

/* 颗粒层：深色颗粒压一点，浅色碎点提一点 */
.brand-seal-grain {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.brand-seal-grain-dark {
  fill: var(--seal-deep);
  opacity: 0.55;
}

.brand-seal-grain-light {
  fill: var(--paper);
  opacity: 0.16;
}

/* 内白描边 */
.brand-seal-ring {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  border: 0.04em solid var(--paper);
  border-radius: 0.05em;
  opacity: 0.78;
}

/* 印文：楷体加粗 + 纵向轻拉，凑一点碑刻的方正 */
.brand-seal-char {
  position: relative;
  font-family: var(--font-display);
  font-size: 0.56em;
  font-weight: 700;
  line-height: 1;
  color: var(--paper);
  letter-spacing: 0;
  transform: scaleY(1.08);
}
</style>
