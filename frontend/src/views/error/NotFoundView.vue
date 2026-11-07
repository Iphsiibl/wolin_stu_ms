<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <div class="nf-inner">
      <div class="nf-code">404</div>
      <span class="page-eyebrow">Not found</span>
      <h1 class="nf-title">页面不存在</h1>
      <p class="nf-desc">你访问的页面可能已被移动、改名或删除</p>
      <el-button type="primary" @click="router.push('/stat/analysis')">返回首页</el-button>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background-color: var(--canvas);
}

.nf-inner {
  padding: 48px 64px;
  text-align: center;
  background-color: var(--paper);
  border: 1px solid var(--rule);
  border-top: 2px solid var(--ink-900);
  border-radius: var(--radius-lg);
}

/* 大号等宽数字：像台账上缺了一页的页码 */
.nf-code {
  margin-bottom: 10px;
  font-family: var(--font-mono);
  font-size: 76px;
  font-weight: 600;
  line-height: 1;
  color: var(--rule-strong);
  letter-spacing: 0.04em;
}

.nf-title {
  margin: 6px 0 0;
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 400;
  color: var(--text-ink);
  letter-spacing: 3px;
}

.nf-desc {
  margin: 10px 0 26px;
  font-size: 13px;
  color: var(--text-sub);
}

@media (max-width: 560px) {
  .nf-inner {
    padding: 36px 28px;
  }

  .nf-code {
    font-size: 56px;
  }
}
</style>
