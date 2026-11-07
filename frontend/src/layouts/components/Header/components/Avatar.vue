<template>
  <el-dropdown trigger="click">
    <div class="avatar header-avatar">
      <img src="@/assets/images/avatar-admin.jpg" alt="管理员头像" />
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item disabled>
          <el-icon><User /></el-icon>{{ userStore.user?.displayName }}（{{ userStore.user?.role }}）
        </el-dropdown-item>
        <el-dropdown-item divided @click="logout">
          <el-icon><SwitchButton /></el-icon>退出登录
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";

import { LOGIN_URL } from "@/config";
import { useUserStore } from "@/store/user";

import { User, SwitchButton } from "@element-plus/icons-vue";

const router = useRouter();
const userStore = useUserStore();

/**
 * 退出登录。
 *
 * 本项目后端没有鉴权接口，这里清掉前端保存的登录态即可。
 */
const logout = async () => {
  try {
    await ElMessageBox.confirm("您是否确认退出登录?", "温馨提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning"
    });
    userStore.logout();
    router.replace(LOGIN_URL);
    ElMessage.success("退出登录成功！");
  } catch {
    // 用户点了取消
  }
};
</script>

<style scoped lang="scss">
.avatar {
  width: 32px;
  height: 32px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid rgb(255 255 255 / 22%);
  border-radius: 50%;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;

  &:hover {
    border-color: var(--seal);
    box-shadow: 0 0 0 2px rgb(212 160 74 / 26%);
    transform: translateY(-1px);
  }

  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}
</style>
