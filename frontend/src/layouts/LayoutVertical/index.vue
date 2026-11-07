<!--
  竖向布局 —— 「教务墨册」

    ┌──────┬──────────────────────────────────────────────┐
    │ 印   │ 顶栏（墨）：折叠 · 面包屑          工具组 头像 │
    │ 章   ├──────────────────────────────────────────────┤
    │ 竖   │ 多页签（纸）                                  │
    │ 排   ├──────────────────────────────────────────────┤
    │ 标   │ 内容区（霜）                                  │
    │ 题   │                                              │
    │ 菜   │                                              │
    │ 单   │                                              │
    └──────┴──────────────────────────────────────────────┘

  左侧是「书脊」：一条 56px 的墨色窄条，顶端是朱砂印章，
  下面竖排写着系统名；右边是目录。折叠时窄条变成图标栏。
-->
<template>
  <el-container class="layout">
    <el-aside>
      <div
        class="aside-box"
        :class="{ 'is-collapsed': collapsed }"
        :style="{ width: collapsed ? '64px' : '226px' }"
      >
        <!-- 书脊：印章 + 竖排标题 -->
        <div class="spine-rail">
          <BrandSeal class="spine-seal" :size="34" />
          <div v-show="!collapsed" class="spine-title">学生管理系统</div>
        </div>

        <!-- 目录 -->
        <div class="spine-menu">
          <div v-show="!collapsed" class="spine-label">目录</div>
          <el-scrollbar>
            <el-menu
              :router="false"
              :default-active="activeMenu"
              :collapse="collapsed"
              :unique-opened="accordion"
              :collapse-transition="false"
            >
              <SubMenu :menu-list="menuList" />
            </el-menu>
          </el-scrollbar>
        </div>
      </div>
    </el-aside>
    <el-container>
      <el-header>
        <ToolBarLeft />
        <ToolBarRight />
      </el-header>
      <Main />
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import ToolBarLeft from "@/layouts/components/Header/ToolBarLeft.vue";
import ToolBarRight from "@/layouts/components/Header/ToolBarRight.vue";
import Main from "@/layouts/components/Main/index.vue";
import SubMenu from "@/layouts/components/Menu/SubMenu.vue";
import BrandSeal from "@/components/BrandSeal/index.vue";
import { useAuthStore } from "@/stores/modules/auth";
import { useGlobalStore } from "@/stores/modules/global";

const route = useRoute();
const authStore = useAuthStore();
const globalStore = useGlobalStore();
const accordion = computed(() => globalStore.accordion);
const isCollapse = computed(() => globalStore.isCollapse);
const menuList = computed(() => authStore.showMenuListGet);
const activeMenu = computed(() => (route.meta.activeMenu ? route.meta.activeMenu : route.path) as string);

/**
 * 窄屏时把书脊目录自动收成图标栏。
 *
 * 目录本身是定宽的（展开 226px），窄屏上会把内容区挤成一条缝，
 * 连标题都放不下，整页还会多出一条横向滚动条。
 *
 * 这里用的是一个【只存在于本次会话】的临时状态，
 * 不写进 global store —— 用户自己折叠/展开的偏好不会被窄屏改掉。
 */
const NARROW_BREAKPOINT = 768;
const viewportWidth = ref(typeof window === "undefined" ? 1440 : window.innerWidth);
const isNarrow = computed(() => viewportWidth.value < NARROW_BREAKPOINT);
/** 实际生效的折叠状态 = 用户折叠 或 窄屏强制 */
const collapsed = computed(() => isCollapse.value || isNarrow.value);

const handleResize = () => {
  viewportWidth.value = window.innerWidth;
};

onMounted(() => window.addEventListener("resize", handleResize));
onBeforeUnmount(() => window.removeEventListener("resize", handleResize));
</script>

<style scoped lang="scss">
@use "./index";

/* 书脊顶端的品牌印章：印面由 BrandSeal 组件自带，这里只管摆位 */
.spine-seal {
  flex-shrink: 0;
}
</style>
