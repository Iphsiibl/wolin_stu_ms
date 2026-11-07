<template>
  <div :class="['breadcrumb-box mask-image', !globalStore.breadcrumbIcon && 'no-icon']">
    <el-breadcrumb :separator-icon="ArrowRight">
      <transition-group name="breadcrumb">
        <el-breadcrumb-item v-for="(item, index) in breadcrumbList" :key="item.path">
          <div
            class="el-breadcrumb__inner is-link"
            :class="{ 'item-no-icon': !item.meta.icon }"
            @click="onBreadcrumbClick(item, index)"
          >
            <el-icon v-if="item.meta.icon && globalStore.breadcrumbIcon" class="breadcrumb-icon">
              <component :is="item.meta.icon"></component>
            </el-icon>
            <span class="breadcrumb-title">{{ item.meta.title }}</span>
          </div>
        </el-breadcrumb-item>
      </transition-group>
    </el-breadcrumb>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, HomeFilled } from "@element-plus/icons-vue";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { HOME_URL } from "@/config";
import type { MenuOptions } from "@/stores/interface";
import { useAuthStore } from "@/stores/modules/auth";
import { useGlobalStore } from "@/stores/modules/global";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const globalStore = useGlobalStore();

const breadcrumbList = computed(() => {
  const matchedPath = route.matched[route.matched.length - 1]?.path ?? route.path;
  let breadcrumbData = authStore.breadcrumbListGet[matchedPath] ?? [];
  // 🙅‍♀️不需要首页面包屑可删除以下判断
  if (!breadcrumbData.length || breadcrumbData[0].path !== HOME_URL) {
    breadcrumbData = [{ path: HOME_URL, meta: { icon: HomeFilled, title: "首页" } }, ...breadcrumbData];
  }
  return breadcrumbData;
});

// Click Breadcrumb
const onBreadcrumbClick = (item: MenuOptions, index: number) => {
  if (index !== breadcrumbList.value.length - 1) router.push(item.path);
};
</script>

<style scoped lang="scss">
.breadcrumb-box {
  display: flex;
  align-items: center;
  overflow: hidden;
  .el-breadcrumb {
    white-space: nowrap;
    .el-breadcrumb__item {
      position: relative;
      float: none;
      display: inline-block;
      .item-no-icon {
        transform: translateY(-3px);
      }
      .el-breadcrumb__inner {
        display: inline-flex;
        &.is-link {
          font-size: 13px;
          color: rgb(255 255 255 / 52%);
          &:hover {
            color: rgb(255 255 255 / 88%);
          }
        }
        .breadcrumb-icon {
          margin-top: 1px;
          margin-right: 6px;
          font-size: 15px;
          opacity: 0.7;
        }
        .breadcrumb-title {
          margin-top: 2px;
        }
      }
      /* 当前页：楷体，像文书上的标题 */
      &:last-child .el-breadcrumb__inner,
      &:last-child .el-breadcrumb__inner:hover {
        font-family: var(--font-display);
        font-size: 16px;
        color: #fff;
        letter-spacing: 1px;
      }
      :deep(.el-breadcrumb__separator) {
        font-size: 11px;
        color: rgb(255 255 255 / 28%);
        transform: translateY(-1px);
      }
    }
  }
}
.no-icon {
  .el-breadcrumb {
    .el-breadcrumb__item {
      top: -2px;
      :deep(.el-breadcrumb__separator) {
        top: 4px;
      }
      .item-no-icon {
        transform: translateY(0);
      }
    }
  }
}
</style>
