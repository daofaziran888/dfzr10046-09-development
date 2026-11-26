<template>
  <section class="apply-panel" data-testid="publish-apply-panel">
    <header class="apply-head">
      <h3>凭有效快照签核单创建维度发布申请</h3>
      <p class="muted small">
        双人签核通过后会生成发布待办；只有状态为「已签核」、修订与当前快照一致且未被使用/撤回的单才能开单。
        开单与签核页的撤回并行提交时，由后端原子裁决，只有一个操作生效。
      </p>
    </header>

    <div v-if="!signoffs.length" class="empty-state">
      暂无快照签核单，请先到「快照签核单」页制单并由另一位操作员确认。
      <RouterLink class="link" to="/snapshot_signoff">前往签核页面 →</RouterLink>
    </div>

    <template v-else>
      <div class="todo-block" data-testid="publish-todo-list">
        <span class="todo-title">维度发布待办（签核通过且有效）：</span>
        <span v-if="!todos.length" class="muted small">当前没有可开单的有效签核待办</span>
        <button
          v-for="todo in todos"
          :key="todo.id"
          type="button"
          class="todo-chip"
          :data-testid="`todo-${todo.id}`"
          @click="selectSignoff(String(todo.id))"
        >
          {{ todo.签核单编号 }} · {{ todo.快照编号 }} · {{ todo.修订号 }}
          <span class="link">凭此单开单</span>
        </button>
      </div>

      <div class="apply-grid">
        <label class="create-field span-2">
          <span>选择快照签核单（可粘贴签核单编号）</span>
          <select
            v-model="selectedRef"
            data-testid="signoff-select"
            @change="onSelectChange"
          >
            <option value="">— 请选择已签核的快照签核单 —</option>
            <option v-for="so in signoffs" :key="so.id" :value="String(so.id)">
              #{{ so.id }} {{ so.签核单编号 }}｜{{ so.快照编号 }}｜{{ so.修订号 }}｜{{ so.status }}
            </option>
          </select>
          <input
            class="no-select-ref"
            v-model="signoffNoInput"
            data-testid="signoff-no-input"
            placeholder="或直接填写/粘贴签核单编号，如 QH-CUST-20261001-R1"
            @input="onNoInput"
          />
        </label>

        <div v-if="selected" class="signoff-detail span-2" data-testid="selected-signoff-detail">
          <div class="detail-line">
            <strong>{{ selected.签核单编号 }}</strong>
            <span :class="['usable-badge', selected.usable ? 'ok' : 'bad']" data-testid="selected-usability">
              {{ selected.usable ? '✓ 该签核单仍可使用' : '✕ 该签核单不可使用' }}
            </span>
          </div>
          <div>
            快照 {{ selected.快照编号 }} · 签核修订
            <strong data-testid="selected-revision">{{ selected.修订号 }}</strong>
            · 制单人 {{ selected.制单人 }} · 签核人 {{ selected.签核人 }}
          </div>
          <div class="small" :class="selected.usable ? 'ok-text' : 'error-text'" data-testid="selected-usability-reason">
            {{ selected.usability_reason }}
          </div>
          <div class="small next-step" data-testid="selected-next-step">{{ selected.next_step }}</div>
        </div>

        <label class="create-field">
          <span>发布人</span>
          <input v-model="form.发布人" data-testid="publish-operator" :list="operatorListId" placeholder="发布操作员" />
        </label>
        <label class="create-field">
          <span>发布版本（留空自动生成）</span>
          <input v-model="form.发布版本" data-testid="publish-version" placeholder="例如 v20261126" />
        </label>
        <label class="create-field">
          <span>发布编号（留空自动生成）</span>
          <input v-model="form.发布编号" data-testid="publish-no" placeholder="例如 PUB-CUST-v2" />
        </label>
        <label class="create-field">
          <span>可见范围</span>
          <select v-model="form.可见范围" data-testid="publish-scope">
            <option value="内部">内部</option>
            <option value="全量">全量</option>
            <option value="指定下游">指定下游</option>
          </select>
        </label>
        <label class="create-field span-2">
          <span>说明 / 申请说明</span>
          <textarea
            v-model="form.申请说明"
            data-testid="publish-description"
            rows="3"
            placeholder="请填写发布说明：发布内容、修订对应关系与注意事项"
          ></textarea>
        </label>
      </div>

      <div class="apply-actions">
        <button
          class="btn primary"
          type="button"
          data-testid="submit-publish-apply"
          :disabled="submitting"
          @click="submit"
        >
          {{ submitting ? '提交中…' : '提交并创建发布申请' }}
        </button>
        <button class="btn ghost" type="button" data-testid="reload-signoffs" @click="loadSignoffs">
          重新读取签核状态
        </button>
        <span
          v-if="message"
          :class="['apply-message', messageKind]"
          data-testid="publish-apply-message"
          role="status"
        >{{ message }}</span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'

import { applyPublish, listEntries } from '@/api/backend-service'
import { useOperator } from '@/composables/useOperator'
import type { EntryRow } from '@/data/types'

const props = defineProps<{ initialSignoff?: string }>()
const emit = defineEmits<{ (e: 'applied'): void }>()

const { currentOperator } = useOperator()
const operatorListId = 'operator-options'

const signoffs = ref<EntryRow[]>([])
const selectedRef = ref('')
const signoffNoInput = ref('')
const submitting = ref(false)
const message = ref('')
const messageKind = ref<'ok' | 'err'>('ok')
const form = reactive({
  发布人: currentOperator.value,
  发布版本: '',
  发布编号: '',
  可见范围: '内部',
  申请说明: '',
})

const todos = computed(() => signoffs.value.filter((s) => s.status === '已签核' && s.usable === true))

const selected = computed<EntryRow | null>(() => {
  if (signoffNoInput.value.trim()) {
    const no = signoffNoInput.value.trim()
    return signoffs.value.find((s) => String(s.签核单编号) === no) ?? null
  }
  if (!selectedRef.value) return null
  return signoffs.value.find((s) => String(s.id) === selectedRef.value) ?? null
})

async function loadSignoffs() {
  try {
    const page = await listEntries('snapshot_signoff', { size: '200' })
    signoffs.value = page.items
    // 若父级给了初始选中项，保持选中
    if (props.initialSignoff && !selectedRef.value && !signoffNoInput.value) {
      preselect(props.initialSignoff)
    }
  } catch {
    /* 面板内静默，父页仍有错误区 */
  }
}

function preselect(ref: string) {
  const value = String(ref)
  const byId = signoffs.value.find((s) => String(s.id) === value)
  if (byId) {
    selectedRef.value = value
    signoffNoInput.value = ''
    return
  }
  const byNo = signoffs.value.find((s) => String(s.签核单编号) === value)
  if (byNo) {
    signoffNoInput.value = value
    selectedRef.value = String(byNo.id)
  }
}

function selectSignoff(id: string) {
  selectedRef.value = id
  signoffNoInput.value = ''
  message.value = ''
}

function onSelectChange() {
  signoffNoInput.value = ''
  message.value = ''
}

function onNoInput() {
  // 让编号输入成为新的选择来源；下拉框仅作辅助
  if (signoffNoInput.value.trim()) selectedRef.value = ''
  message.value = ''
}

async function submit() {
  message.value = ''
  if (!selected.value) {
    messageKind.value = 'err'
    message.value = '请先选择或填写一张快照签核单'
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      signoff_id: selected.value.id,
      签核单编号: selected.value.签核单编号,
      申请说明: form.申请说明,
      说明: form.申请说明,
      发布人: form.发布人 || currentOperator.value,
      operator: form.发布人 || currentOperator.value,
      可见范围: form.可见范围,
    }
    if (form.发布版本.trim()) payload.发布版本 = form.发布版本.trim()
    if (form.发布编号.trim()) payload.发布编号 = form.发布编号.trim()

    const result = await applyPublish(payload)
    messageKind.value = result.ok ? 'ok' : 'err'
    message.value = result.message
    if (result.ok) {
      // 保留说明文本无意义了，清空编号/版本但保留说明也可；这里重置选择并通知父表刷新
      form.发布版本 = ''
      form.发布编号 = ''
      selectedRef.value = ''
      signoffNoInput.value = ''
      emit('applied')
    } else {
      // 冲突后刷新签核最新状态（可能已被撤回或已使用）
      await loadSignoffs()
      emit('applied')
    }
  } catch (error) {
    messageKind.value = 'err'
    message.value = error instanceof Error ? error.message : '发布申请提交失败'
  } finally {
    submitting.value = false
  }
}

function onVisibility() {
  if (document.visibilityState === 'visible') void loadSignoffs()
}

watch(
  () => props.initialSignoff,
  (value) => {
    if (value) preselect(value)
  },
)

onMounted(async () => {
  await loadSignoffs()
  if (props.initialSignoff) preselect(props.initialSignoff)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => document.removeEventListener('visibilitychange', onVisibility))

defineExpose({ loadSignoffs })
</script>

<style scoped>
.apply-panel { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; margin-bottom: 16px; }
.apply-head h3 { margin: 0 0 4px; font-size: 16px; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.todo-block { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background: #f8fafc; border-radius: 8px; padding: 10px; margin: 10px 0; }
.todo-title { font-size: 13px; font-weight: 600; }
.todo-chip { border: 1px solid #b2ccff; background: #eff4ff; border-radius: 999px; padding: 4px 12px; font-size: 12px; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
.apply-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
.create-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.create-field input, .create-field select, .create-field textarea { border: 1px solid var(--border); border-radius: 6px; padding: 8px; font-size: 13px; color: #1f2937; font-family: inherit; }
.span-2 { grid-column: 1 / -1; }
.no-select-ref { margin-top: 6px; }
.signoff-detail { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; display: grid; gap: 4px; font-size: 13px; }
.detail-line { display: flex; align-items: center; gap: 10px; }
.usable-badge { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.usable-badge.ok { background: #ecfdf3; color: #067647; }
.usable-badge.bad { background: #fef3f2; color: #b42318; }
.ok-text { color: #067647; }
.error-text { color: #b42318; }
.next-step { color: #334155; }
.apply-actions { display: flex; align-items: center; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
.apply-message { font-size: 13px; padding: 6px 10px; border-radius: 6px; }
.apply-message.ok { background: #ecfdf3; color: #067647; border: 1px solid #6ce9a6; }
.apply-message.err { background: #fef3f2; color: #b42318; border: 1px solid #fda29b; }
.empty-state { color: var(--muted); font-size: 13px; padding: 12px 0; display: flex; gap: 10px; align-items: center; }
</style>
