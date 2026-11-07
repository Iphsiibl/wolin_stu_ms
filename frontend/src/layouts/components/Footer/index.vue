<template>
  <div class="footer">
    <span class="footer-name">{{ title }}</span>
    <span class="footer-stack">{{ stack }}</span>
  </div>
</template>

<script setup lang="ts">
import { APP_TITLE } from "@/config";

const title = APP_TITLE;
const stack = "Vue 3 · Element Plus · FastAPI";
</script>

<style scoped lang="scss">
@use "./index";
</style>
