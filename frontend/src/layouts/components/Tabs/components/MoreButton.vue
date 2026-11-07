<template>
  <el-dropdown trigger="click" :teleported="false">
    <div class="more-button">
      <i :class="'iconfont icon-xiala'"></i>
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item @click="refresh">
          <el-icon><Refresh /></el-icon>刷新当前页
        </el-dropdown-item>
        <el-dropdown-item @click="maximize">
          <el-icon><FullScreen /></el-icon>最大化当前页
        </el-dropdown-item>
        <el-dropdown-item divided @click="closeCurrentTab">
          <el-icon><Remove /></el-icon>关闭当前页
        </el-dropdown-item>
        <el-dropdown-item @click="tabStore.closeTabsOnSide(route.fullPath, 'left')">
          <el-icon><DArrowLeft /></el-icon>关闭左侧页签
        </el-dropdown-item>
        <el-dropdown-item @click="tabStore.closeTabsOnSide(route.fullPath, 'right')">
          <el-icon><DArrowRight /></el-icon>关闭右侧页签
        </el-dropdown-item>
        <el-dropdown-item divided @click="tabStore.closeMultipleTab(route.fullPath)">
          <el-icon><CircleClose /></el-icon>关闭其它页签
        </el-dropdown-item>
        <el-dropdown-item @click="closeAllTab">
          <el-icon><FolderDelete /></el-icon>关闭全部页签
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { inject, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  CircleClose,
  DArrowLeft,
  DArrowRight,
  FolderDelete,
  FullScreen,
  Refresh,
  Remove,
} from "@element-plus/icons-vue";

import { HOME_URL } from "@/config";
import { useGlobalStore } from "@/stores/modules/global";
import { useKeepAliveStore } from "@/stores/modules/keepAlive";
import { useTabsStore } from "@/stores/modules/tabs";

const route = useRoute();
const router = useRouter();
const tabStore = useTabsStore();
const globalStore = useGlobalStore();
const keepAliveStore = useKeepAliveStore();

// refresh current page
const refreshCurrentPage = inject<(val: boolean) => void>("refresh");

const refresh = () => {
  setTimeout(() => {
    if (route.meta.isKeepAlive) {
      keepAliveStore.removeKeepAliveName(route.fullPath);
    }

    if (refreshCurrentPage) {
      refreshCurrentPage(false);
      nextTick(() => {
        if (route.meta.isKeepAlive) {
          keepAliveStore.addKeepAliveName(route.fullPath);
        }
        refreshCurrentPage(true);
      });
    }
  }, 0);
};

// maximize current page
const maximize = () => {
  globalStore.maximize = true;
};

// Close Current
const closeCurrentTab = () => {
  if (route.meta.isAffix) return;
  tabStore.removeTabs(route.fullPath);
};

// Close All
const closeAllTab = () => {
  tabStore.closeMultipleTab();
  router.push(HOME_URL);
};
</script>

<style scoped lang="scss">
@use "../index";
</style>
