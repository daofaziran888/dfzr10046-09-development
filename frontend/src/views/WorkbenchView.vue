<template>
  <section class="page" :data-module="meta.key">
   <div class="page-body" :inert="showCreate" :aria-hidden="showCreate ? 'true' : undefined">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <RouterLink
          v-if="meta.key === 'dim_snapshot'"
          class="btn"
          data-testid="goto-signoff-page"
          to="/snapshot_signoff"
        >双人签核记录</RouterLink>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <div
      v-if="actionMessage"
      :class="['flow-message', actionOk ? 'ok' : 'err']"
      data-testid="action-message"
      role="status"
    >{{ actionMessage }}</div>

    <!-- 维度发布页：凭有效签核单开单的跨模块入口 -->
    <PublishApplyPanel
      v-if="meta.key === 'dim_publish'"
      ref="applyPanelRef"
      :initial-signoff="initialSignoff"
      @applied="reload"
    />

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th v-if="meta.key === 'dim_snapshot'">双人签核</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
          <td v-if="meta.key === 'dim_snapshot'" :data-testid="`snapshot-signoff-cell-${row.id}`">
            <template v-if="latestSignoff(row)">
              <span :class="['mini-badge', latestSignoff(row)?.usable ? 'ok' : latestSignoff(row)?.status === '已签核' ? 'bad' : 'neutral']">
                {{ latestSignoff(row)?.status }}
              </span>
              <div class="small muted">{{ latestSignoff(row)?.签核单编号 }} · {{ latestSignoff(row)?.修订号 }}</div>
              <div v-if="latestSignoff(row)?.usable" class="small ok-text">可用于发布开单</div>
              <div v-else class="small error-text">{{ shortReason(latestSignoff(row)) }}</div>
              <div class="cell-links">
                <RouterLink
                  class="link"
                  :data-testid="`view-signoff-${row.id}`"
                  :to="`/snapshot_signoff?signoff=${latestSignoff(row)?.id}`"
                >查看签核单</RouterLink>
                <button
                  class="link"
                  type="button"
                  :data-testid="`snapshot-create-signoff-${row.id}`"
                  @click="goCreateSignoff(row)"
                >重新发起</button>
              </div>
            </template>
            <template v-else>
              <span class="small muted">尚无签核单</span>
              <div>
                <button
                  class="link strong-link"
                  type="button"
                  :data-testid="`snapshot-create-signoff-${row.id}`"
                  @click="goCreateSignoff(row)"
                >发起快照签核</button>
              </div>
            </template>
          </td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <template v-for="action in meta.actions" :key="action">
              <span
                v-if="meta.key === 'dim_snapshot' && action === '发起签核'"
                class="alias-hook"
                :data-testid="`action-${row.id}-快照签核`"
              >
                <span class="alias-hook" :data-testid="`action-${row.id}-申请签核`">
                  <button
                    class="link strong-link"
                    type="button"
                    :data-testid="`action-${row.id}-发起签核`"
                    @click="goCreateSignoff(row)"
                  >
                    {{ action }}
                  </button>
                </span>
              </span>
              <button
                v-else
                class="link"
                type="button"
                :data-testid="`action-${row.id}-${action}`"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2 + (meta.key === 'dim_snapshot' ? 1 : 0)" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>
   </div><!-- /page-body -->

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal" role="dialog" aria-modal="true" :aria-label="`登记${meta.entity}`">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input
            v-model="createValues[field]"
            :data-testid="`create-${field}`"
            :required="isRequired(field)"
          />
        </label>
        <p v-if="createError" class="error-text" data-testid="create-error" role="alert">{{ createError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记并提交' }}
          </button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text" data-testid="page-error">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PublishApplyPanel from '@/components/PublishApplyPanel.vue'
import {
  createEntry,
  downloadEntries,
  listEntries,
  moduleMeta,
  runAction as applyAction,
} from '@/api/backend-service'
import type { EntryRow } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const route = useRoute()
const router = useRouter()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const signoffRows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const actionMessage = ref('')
const actionOk = ref(true)
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})
const createError = ref('')
const applyPanelRef = ref<InstanceType<typeof PublishApplyPanel> | null>(null)

const initialSignoff = computed(() => {
  const q = route.query.signoff
  return q === undefined ? '' : String(Array.isArray(q) ? q[0] : q)
})

const STAT_STATUS_OVERRIDE: Record<string, [string, string]> = {
  dim_publish: ['待发布', '已发布'],
}

const stats = computed(() => {
  const override = STAT_STATUS_OVERRIDE[meta.key]
  const secondStatus = override?.[0] ?? meta.statuses[1]
  const thirdStatus = override?.[1] ?? meta.statuses[meta.statuses.length - 1]
  const secondLabel = override ? `${secondStatus}申请` : meta.metrics[1]
  const thirdLabel = override ? `${thirdStatus}版本` : meta.metrics[2]
  return [
    { label: meta.metrics[0], value: total.value },
    { label: secondLabel, value: rows.value.filter((row) => row.status === secondStatus).length },
    { label: thirdLabel, value: rows.value.filter((row) => row.status === thirdStatus).length },
  ]
})
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

function isRequired(field: string): boolean {
  return !!meta.requiredFields?.includes(field)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  createError.value = ''
  actionMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  createError.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) {
      createError.value = result.message
      actionOk.value = false
      actionMessage.value = result.message
      return
    }
    showCreate.value = false
    actionOk.value = true
    actionMessage.value = result.message || `${meta.entity}已登记`
    await reload()
    if (meta.key === 'dim_publish' && applyPanelRef.value) {
      await applyPanelRef.value.loadSignoffs()
    }
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: EntryRow) {
  errorMessage.value = ''
  actionMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action)
    actionOk.value = result.ok
    actionMessage.value = result.message
    if (!result.ok) errorMessage.value = result.message
    await reload()
  } catch (error) {
    actionOk.value = false
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
    actionMessage.value = errorMessage.value
  }
}

async function loadSignoffs() {
  if (meta.key !== 'dim_snapshot') return
  try {
    const page = await listEntries('snapshot_signoff', { size: '200' })
    signoffRows.value = page.items
  } catch {
    /* 签核状态加载失败不阻塞快照表 */
  }
}

function latestSignoff(snapshotRow: EntryRow): EntryRow | null {
  const matches = signoffRows.value.filter((so) => {
    if (so.snapshot_id !== undefined && Number(so.snapshot_id) === Number(snapshotRow.id)) return true
    return String(so.快照编号 ?? '') === String(snapshotRow.快照编号 ?? '')
  })
  if (!matches.length) return null
  return matches.reduce((a, b) => (Number(a.id) > Number(b.id) ? a : b))
}

function shortReason(row: EntryRow | null): string {
  if (!row) return ''
  const reason = String(row.usability_reason ?? '')
  return reason.length > 42 ? `${reason.slice(0, 42)}…` : reason
}

function goCreateSignoff(row: EntryRow) {
  void router.push({ path: '/snapshot_signoff', query: { newFor: String(row.id) } })
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, { ...filters.value, size: '200' })
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
  await loadSignoffs()
}

function onVisibility() {
  if (document.visibilityState === 'visible') void reload()
}

watch(
  () => props.moduleKey,
  async () => {
    filters.value = {}
    await reload()
  },
)

onMounted(() => {
  void reload()
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => document.removeEventListener('visibilitychange', onVisibility))
</script>

<style scoped>
.flow-message { padding: 8px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.flow-message.ok { background: #ecfdf3; border: 1px solid #6ce9a6; color: #067647; }
.flow-message.err { background: #fef3f2; border: 1px solid #fda29b; color: #b42318; }
.small { font-size: 12px; }
.muted { color: var(--muted); }
.ok-text { color: #067647; }
.error-text { color: #b42318; }
.cell-links { display: flex; gap: 8px; margin-top: 2px; }
.alias-hook { display: inline; }
.strong-link { font-weight: 600; }
.mini-badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; background: #eef2f6; }
.mini-badge.ok { background: #ecfdf3; color: #067647; }
.mini-badge.bad { background: #fffaeb; color: #b54708; }
.mini-badge.neutral { background: #f2f4f7; color: #475467; }
.page-actions { display: flex; gap: 8px; align-items: center; }
</style>
