<template>
  <el-icon class="collapse-icon" @click="changeCollapse">
    <component :is="globalStore.isCollapse ? 'expand' : 'fold'"></component>
  </el-icon>
</template>

<script setup lang="ts">
import { useGlobalStore } from "@/stores/modules/global";

const globalStore = useGlobalStore();
const changeCollapse = () => globalStore.setGlobalState("isCollapse", !globalStore.isCollapse);
</script>

<style scoped lang="scss">
.collapse-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  margin-right: 12px;
  font-size: 18px;
  color: rgb(255 255 255 / 62%);
  cursor: pointer;
  border-radius: var(--radius);
  transition:
    color 0.16s ease,
    background-color 0.16s ease;

  &:hover {
    color: #fff;
    background-color: rgb(255 255 255 / 9%);
  }
}
</style>
