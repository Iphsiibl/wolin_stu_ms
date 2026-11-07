/**
 * =====================================================================
 * 登录页（纯前端模拟）
 * =====================================================================
 * 后端没有鉴权接口，所以这个页面不做真正的身份验证。
 * 它的作用是：演示登录流程 + 保护路由（未登录访问页面会被守卫踢回来）。
 *
 * 演示账号：admin / 任意密码（推荐 admin / 123456）
 *
 * 版式：左右分栏 —— 左边是墨色的「书脊」，右边是纸面的表单。
 * =====================================================================
 */
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'

import { useUserStore } from '@/store/user'
import BrandSeal from '@/components/BrandSeal/index.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '123456',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

/** 提交登录 */
async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    userStore.login(form.username, form.password)
    ElMessage.success('登录成功，欢迎回来')
    // 登录前想去的页面优先回去，否则回首页
    // （首页 = 统计分析，数据看板已并入该页）
    const redirect = (route.query.redirect as string) || '/stat/analysis'
    router.push(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // 已登录直接进首页
  if (userStore.isLoggedIn()) {
    router.replace('/stat/analysis')
  }
})
</script>

<template>
  <div class="login-page">
    <!-- 左：书脊 -->
    <section class="spine">
      <div class="seal-mark">
        <BrandSeal :size="40" />
      </div>

      <div class="brand-row">
        <h1 class="brand-title">学生管理系统</h1>
        <div class="brand-side">
          <span class="brand-rule" />
          <p class="brand-en">Student Management System</p>
          <p class="brand-desc">
            学员档案 · 成绩考核 · 就业去向<br />
            一册在手，随时对账
          </p>
        </div>
      </div>

      <p class="spine-foot">Vue 3 · Element Plus · FastAPI</p>
    </section>

    <!-- 右：表单 -->
    <section class="form-side">
      <div class="form-inner">
        <span class="page-eyebrow">Sign in</span>
        <h2 class="form-title">登录</h2>
        <p class="form-note">请使用教务账号进入系统</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" clearable>
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              show-password
              clearable
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 演示模式提示：朱砂左边条，像批注 -->
        <div class="demo-note">
          <span class="demo-tag">演示模式</span>
          <p>后端暂未提供登录接口，此处为前端模拟登录，任意账号密码均可进入。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  background-color: var(--paper);
}

/* ---------------------------------------------------------------------
 * 左：墨色书脊
 * ------------------------------------------------------------------ */
.spine {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex-shrink: 0;
  width: 46%;
  max-width: 620px;
  min-width: 340px;
  padding: 48px 56px 40px;
  background-color: var(--ink-900);
}

/* 品牌印章：印面由 BrandSeal 组件自带，这里只管摆位。
   左对齐，跟下面的竖排书名同一条轴 —— 居中会变成一枚孤零零挂在半空的印。 */
.seal-mark {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.brand-row {
  display: flex;
  align-items: flex-start;
  gap: 30px;
}

/* 竖排书名 */
.brand-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 400;
  line-height: 1.1;
  color: rgb(255 255 255 / 92%);
  letter-spacing: 0.28em;
  writing-mode: vertical-rl;
  text-orientation: upright;
}

.brand-side {
  padding-top: 6px;
}

.brand-rule {
  display: block;
  width: 44px;
  height: 2px;
  margin-bottom: 16px;
  background-color: var(--seal);
}

.brand-en {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: rgb(255 255 255 / 42%);
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.brand-desc {
  margin: 14px 0 0;
  font-size: 13px;
  line-height: 1.9;
  color: rgb(255 255 255 / 62%);
}

.spine-foot {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgb(255 255 255 / 28%);
  letter-spacing: 0.12em;
}

/* ---------------------------------------------------------------------
 * 右：纸面表单
 * ------------------------------------------------------------------ */
.form-side {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
  background-color: var(--paper);
}

.form-inner {
  width: 100%;
  max-width: 360px;
}

.form-title {
  margin: 4px 0 0;
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 400;
  line-height: 1.2;
  color: var(--text-ink);
  letter-spacing: 4px;
}

.form-note {
  margin: 8px 0 30px;
  padding-bottom: 18px;
  font-size: 13px;
  color: var(--text-sub);
  border-bottom: 1px solid var(--rule);
}

.login-form {
  .el-form-item {
    margin-bottom: 18px;
  }

  .el-input__wrapper {
    padding: 0 14px;
    background-color: var(--wash);
    border-radius: var(--radius);
  }
}

.login-btn {
  width: 100%;
  height: 42px;
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 6px;
}

/* 演示模式提示：朱砂左边条 */
.demo-note {
  margin-top: 26px;
  padding: 12px 14px;
  background-color: var(--seal-soft);
  border-left: 3px solid var(--seal);
  border-radius: 0 var(--radius) var(--radius) 0;

  .demo-tag {
    display: block;
    margin-bottom: 3px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--seal);
    letter-spacing: 1px;
  }

  p {
    margin: 0;
    font-size: 12px;
    line-height: 1.7;
    color: #8a534b;
  }
}

/* ---------------------------------------------------------------------
 * 窄屏：只留表单
 * ------------------------------------------------------------------ */
@media (max-width: 860px) {
  .spine {
    display: none;
  }

  .form-side {
    padding: 32px 20px;
  }
}
</style>
