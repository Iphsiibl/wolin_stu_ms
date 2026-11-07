<!--
  =====================================================================
  学号选择器（就业信息专用）
  ---------------------------------------------------------------------
  【为什么单独抽一个组件】
  就业信息是「一个学生只能有一条就业记录」的模块，所以学号不是自由输入框：
    - 新增时：只能从【还没登记就业信息】的学生里挑，避免重复登记；
    - 编辑时：学号已经落库，必须锁死，只允许改就业内容。
  这两种状态 + 加载中 + 空列表，一共四种情况。
  如果把这些判断写回列表页的模板里，列表页就会背上业务分支，
  后面再加工资区间、批次筛选只会越堆越乱。
  所以这里把「四种状态」整个收进组件，列表页只管传参。

  【用法】
    <StudentSelectField
      v-model="form.stu_id"
      :options="selectableStudents"
      :loading="loadingStudents"
      :locked="editingId !== null"
      :locked-label="`${form.stu_id} · ${editingStudentName}`"
    />
-->
<script setup lang="ts">
import { computed } from 'vue'
import { Lock } from '@element-plus/icons-vue'

/** 候选项：只要列表页能给出来的最小字段集 */
export interface StudentOption {
  stu_id: number
  stu_name: string
  class_name?: string | null
}

const props = withDefaults(
  defineProps<{
    /** 当前选中的学号 */
    modelValue?: number | null
    /** 候选学生（未就业的学生） */
    options?: StudentOption[]
    /** 候选列表是否还在加载 */
    loading?: boolean
    /** 锁定模式：编辑已有记录时为 true，学号不可改 */
    locked?: boolean
    /** 锁定时展示的文案，一般是「学号 · 姓名」 */
    lockedLabel?: string
    /** 未找到候选时的兜底文案 */
    emptyText?: string
  }>(),
  {
    modelValue: null,
    options: () => [],
    loading: false,
    locked: false,
    lockedLabel: '',
    emptyText: '没有可选的学生：可能都已经登记过就业信息了',
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()

/** 有候选可挑（加载完且列表非空） */
const hasOptions = computed(() => props.options.length > 0)

/** 空态：没在加载、但一个候选都没有 */
const showEmptyHint = computed(() => !props.loading && !props.locked && !hasOptions.value)

/** 选项上显示的文案：学号 · 姓名（班级） */
function optionLabel(item: StudentOption): string {
  const base = `${item.stu_id} · ${item.stu_name}`
  return item.class_name ? `${base}（${item.class_name}）` : base
}
</script>

<template>
  <div class="student-field">
    <!-- 编辑态：学号已落库，锁死只读 -->
    <el-input v-if="locked" :model-value="lockedLabel" disabled>
      <template #prefix>
        <el-icon><Lock /></el-icon>
      </template>
    </el-input>

    <!-- 新增态：从真实学生里选 -->
    <el-select
      v-else
      :model-value="modelValue"
      filterable
      :loading="loading"
      placeholder="选择学生"
      style="width: 100%"
      @update:model-value="(val: number | null) => emit('update:modelValue', val)"
    >
      <el-option
        v-for="item in options"
        :key="item.stu_id"
        :label="optionLabel(item)"
        :value="item.stu_id"
      >
        <div class="opt">
          <span class="opt-name">{{ item.stu_name }}</span>
          <span class="opt-meta">
            <span class="num">{{ item.stu_id }}</span>
            <span v-if="item.class_name" class="opt-class">{{ item.class_name }}</span>
          </span>
        </div>
      </el-option>
    </el-select>

    <!-- 空态：说清楚为什么没得选 -->
    <p v-if="showEmptyHint" class="field-empty">{{ emptyText }}</p>
  </div>
</template>

<style scoped>
.student-field {
  width: 100%;
}

/* 下拉项：左边姓名，右边学号与班级，像一本名册 */
.opt {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.opt-name {
  font-size: 13px;
  color: var(--text-ink);
}

.opt-meta {
  display: flex;
  gap: 8px;
  font-size: 11.5px;
  color: var(--text-mute);
}

.opt-class {
  padding: 0 6px;
  background-color: var(--wash);
  border: 1px solid var(--rule-soft);
  border-radius: 2px;
}

/* 空态提示：一句人话 + 朱砂左边条，和登录页的批注条同一套语言 */
.field-empty {
  margin: 6px 0 0;
  padding-left: 8px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-sub);
  border-left: 2px solid var(--seal);
}
</style>
