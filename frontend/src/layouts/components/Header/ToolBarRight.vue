<template>
  <div class="tool-bar-ri">
    <div class="header-icon">
      <!-- 这三个组件都是多根节点（组件 + 弹层），不能往下传 id，
           否则 Vue 会报 "Extraneous non-props attributes" 警告 -->
      <SearchMenu />
      <LogButton />
      <ResetButton />
      <Fullscreen />
    </div>
    <span class="username">{{ username }}</span>
    <Avatar />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useUserStore } from '@/store/user'

import Avatar from './components/Avatar.vue';
import Fullscreen from './components/Fullscreen.vue';
import LogButton from './components/LogButton.vue';
import ResetButton from './components/ResetButton.vue';
import SearchMenu from './components/SearchMenu.vue';

const userStore = useUserStore();
const username = computed(() => userStore.user?.displayName ?? '未登录');
</script>

<style scoped lang="scss">
.tool-bar-ri {
  display: flex;
  align-items: center;
  justify-content: center;

  .header-icon {
    display: flex;
    align-items: center;
    gap: 2px;

    & > * {
      color: rgb(255 255 255 / 62%);
    }
  }

  .username {
    margin: 0 14px 0 10px;
    padding-left: 14px;
    font-size: 13px;
    color: rgb(255 255 255 / 80%);
    border-left: 1px solid rgb(255 255 255 / 14%);
  }
}
</style>
