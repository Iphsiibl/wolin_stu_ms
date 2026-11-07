<template>
  <template v-for="subItem in menuList" :key="subItem.path">
    <el-sub-menu v-if="subItem.children?.length" :index="subItem.path">
      <template #title>
        <el-icon v-if="subItem.meta.icon">
          <component :is="subItem.meta.icon"></component>
        </el-icon>
        <span class="sle">{{ subItem.meta.title }}</span>
      </template>
      <SubMenu :menu-list="subItem.children" />
    </el-sub-menu>
    <el-menu-item v-else :index="subItem.path" @click="handleClickMenu(subItem)">
      <el-icon v-if="subItem.meta.icon">
        <component :is="subItem.meta.icon"></component>
      </el-icon>
      <template #title>
        <span class="sle">{{ subItem.meta.title }}</span>
      </template>
    </el-menu-item>
  </template>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

import type { MenuOptions } from "@/stores/interface";

defineProps<{ menuList: MenuOptions[] }>();

const router = useRouter();
const handleClickMenu = (subItem: MenuOptions) => {
  if (subItem.meta.isLink) return window.open(subItem.meta.isLink, "_blank");
  router.push(subItem.path);
};
</script>

<style lang="scss">
/* =====================================================================
 * 目录样式 —— 墨色底上的细线列表
 *   激活项：文字转白 + 左侧一道 3px 朱砂条（像在目录上盖了个印）
 * ===================================================================== */

.el-menu {
  --el-menu-item-height: 42px;
  --el-menu-sub-item-height: 40px;
  --el-menu-icon-width: 18px;

  .el-menu-item,
  .el-sub-menu__title {
    gap: 2px;
    color: rgb(255 255 255 / 62%);
    transition:
      background-color 0.16s ease,
      color 0.16s ease;
  }

  .el-menu-item {
    padding-left: 18px !important;

    .el-icon {
      font-size: 16px;
      color: rgb(255 255 255 / 45%);
      transition: color 0.16s ease;
    }

    &:hover {
      color: rgb(255 255 255 / 88%);
      background-color: rgb(255 255 255 / 6%);

      .el-icon {
        color: rgb(255 255 255 / 80%);
      }
    }

    &.is-active {
      color: #ffffff;
      background-color: rgb(192 57 43 / 14%);

      .el-icon {
        color: #ffffff;
      }

      /* 左侧朱砂条 */
      &::before {
        position: absolute;
        top: 9px;
        bottom: 9px;
        left: 0;
        width: 3px;
        content: "";
        background-color: var(--seal);
        border-radius: 0 2px 2px 0;
      }
    }
  }

  .el-sub-menu__title:hover {
    color: rgb(255 255 255 / 88%) !important;
    background-color: rgb(255 255 255 / 6%) !important;
  }
}

/* 折叠态：只剩图标，激活项整块朱砂 */
.el-menu--collapse {
  .el-menu-item {
    padding-left: 0 !important;

    &.is-active {
      background-color: var(--seal);

      .el-icon {
        color: #ffffff;
      }

      &::before {
        display: none;
      }
    }
  }
}
</style>
