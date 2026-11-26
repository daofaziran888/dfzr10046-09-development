<template>
  <section class="page" data-module="snapshot_signoff" data-testid="signoff-page">
   <div class="page-body" :inert="anyModal" :aria-hidden="anyModal ? 'true' : undefined">
    <header class="page-head">
      <div>
        <h2>快照签核单</h2>
        <p class="page-desc">
          制单人提交后，必须由另一位操作员确认（同一人将拒绝受理）。签核绑定快照修订与摘要，
          通过后生成维度发布待办；签核可撤回，撤回与发布开单并发时只有一个结果生效。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate()">
          新增快照签核单
        </button>
        <button class="btn" data-testid="reload-signoff" type="button" @click="reload">刷新</button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">导出签核清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value" :data-testid="`stat-${item.key}`">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <div
      v-if="banner.message"
      :class="['flow-banner', banner.kind]"
      data-testid="signoff-message"
      role="status"
    >
      <span>{{ banner.message }}</span>
      <button class="link" type="button" @click="banner.message = ''">知道了</button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>制单人</span>
        <input v-model="filters['制单人']" data-testid="filter-制单人" placeholder="按制单人检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="statusFilter" data-testid="filter-status">
          <option value="">全部状态</option>
          <option v-for="status in meta.statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table" data-testid="signoff-table">
      <thead>
        <tr>
          <th>签核单编号</th>
          <th>快照 / 修订</th>
          <th>所属维度</th>
          <th>制单人 → 签核人</th>
          <th>当前状态</th>
          <th>本单是否还可使用</th>
          <th>下一步</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in pagedRows"
          :key="String(row.id)"
          :data-testid="`row-${row.id}`"
          :data-status="String(row.status)"
          :data-usable="String(!!row.usable)"
          :class="{ highlight: highlightId === Number(row.id) }"
        >
          <td>
            <div class="strong">{{ row.签核单编号 }}</div>
            <div class="muted small">{{ row.签核时间 ? `签核于 ${row.签核时间}` : `提交于 ${row.提交时间 || '—'}` }}</div>
            <div v-if="row.发布申请编号" class="small">
              发布申请：
              <RouterLink :to="`/dim_publish?signoff=${row.id}`" data-testid="linked-publish">
                {{ row.发布申请编号 }}
              </RouterLink>
            </div>
          </td>
          <td>
            <div>{{ row.快照编号 }}</div>
            <div class="small">
              <span class="rev-tag" :data-testid="`signed-revision-${row.id}`">签核修订 {{ row.修订号 }}</span>
              <span class="muted">摘要 {{ row.快照摘要值 || '—' }}</span>
            </div>
          </td>
          <td>{{ row.所属维度 }}</td>
          <td>
            <div>制单：{{ row.制单人 }}</div>
            <div>签核：{{ row.签核人 || '待另一位操作员确认' }}</div>
          </td>
          <td>
            <span :class="['status-badge', statusClass(String(row.status))]">{{ row.status }}</span>
            <div v-if="row.撤回原因" class="muted small">撤回原因：{{ row.撤回原因 }}</div>
            <div v-if="row.失效原因" class="error-text small">{{ row.失效原因 }}</div>
          </td>
          <td>
            <div :data-testid="`usability-${row.id}`" :data-usable="String(!!row.usable)">
              <span :class="['usable-badge', row.usable ? 'ok' : 'bad']">
                {{ row.usable ? '✓ 本单可使用' : '✕ 本单不可使用' }}
              </span>
              <div class="small muted">{{ row.usability_reason }}</div>
            </div>
          </td>
          <td class="next-step" :data-testid="`next-step-${row.id}`">{{ row.next_step }}</td>
          <td class="row-actions wrap">
            <template v-if="row.status === '待签核'">
              <span :data-testid="`action-${row.id}-签核`" class="alias-hook">
                <span :data-testid="`action-${row.id}-签核通过`" class="alias-hook">
                  <button
                    class="link"
                    type="button"
                    :data-testid="`action-${row.id}-确认签核`"
                    @click="openConfirm(row)"
                  >确认签核</button>
                </span>
              </span>
              <span :data-testid="`action-${row.id}-撤回签核`" class="alias-hook">
                <button
                  class="link danger"
                  type="button"
                  :data-testid="`action-${row.id}-撤回`"
                  @click="openWithdraw(row)"
                >撤回</button>
              </span>
            </template>
            <template v-else-if="row.status === '已签核' && row.usable">
              <button
                class="link"
                type="button"
                :data-testid="`goto-publish-${row.id}`"
                @click="goPublish(row)"
              >去发布开单</button>
              <span :data-testid="`action-${row.id}-撤回签核`" class="alias-hook">
                <button
                  class="link danger"
                  type="button"
                  :data-testid="`action-${row.id}-撤回`"
                  @click="openWithdraw(row)"
                >撤回</button>
              </span>
            </template>
            <template v-else-if="row.status === '已使用'">
              <RouterLink class="link" :to="`/dim_publish?signoff=${row.id}`">查看发布申请</RouterLink>
            </template>
            <template v-else-if="row.status === '已撤回' || row.status === '已失效' || row.status === '已驳回'">
              <button
                class="link"
                type="button"
                :data-testid="`action-${row.id}-重新发起`"
                @click="openCreate(row)"
              >按当前修订重新发起签核</button>
            </template>
            <span v-else class="muted">—</span>
          </td>
        </tr>
        <tr v-if="!pagedRows.length">
          <td colspan="8" class="empty-state">暂无快照签核单，可点击右上角「新增快照签核单」</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ filteredRows.length }} 条快照签核记录（{{ filteredRows.length }} 张签核单）</span>
      <span v-if="errorMessage" class="error-text" data-testid="page-error">{{ errorMessage }}</span>
    </footer>
   </div><!-- /page-body：弹窗打开时背景 inert + aria-hidden，避免语义选择器命中背景按钮 -->

    <!-- 制单弹窗：testid 与通用工作台约定保持一致，逐字段保留 create-{字段} 锚点 -->
    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal" role="dialog" aria-modal="true" aria-label="新增快照签核单">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>新增快照签核单（制单提交）</h3>
        <p class="muted small">提交后状态为「待签核」，须由另一位操作员确认；制单人与签核人不能相同。</p>

        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input
            v-model="createValues[field]"
            :data-testid="`create-${field}`"
            :list="listForField(field)"
            :required="isRequired(field)"
            :placeholder="placeholderFor(field)"
          />
        </label>

        <label class="create-field">
          <span>制单说明</span>
          <textarea
            v-model="createRemark"
            data-testid="create-制单说明"
            rows="3"
            placeholder="说明本次签核的快照范围与用途"
          ></textarea>
        </label>

        <div v-if="matchedSnapshot" class="snapshot-hint" data-testid="create-snapshot-hint">
          已选快照 id={{ matchedSnapshot.id }}：{{ matchedSnapshot.所属维度 }} /
          快照日期 {{ matchedSnapshot.快照日期 }} /
          当前修订 <strong data-testid="create-current-revision">{{ matchedSnapshot.修订号 || 'R1' }}</strong>
          / 摘要 {{ matchedSnapshot.快照摘要值 }}
        </div>

        <p v-if="createError" class="error-text" data-testid="create-error" role="alert">{{ createError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认登记并提交' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 双人签核确认弹窗 -->
    <div v-if="confirmRow" class="modal-backdrop" data-testid="confirm-modal" role="dialog" aria-modal="true" aria-label="双人签核确认">
      <form class="modal" @submit.prevent="submitConfirm">
        <h3>双人签核确认</h3>
        <div class="confirm-summary" data-testid="confirm-summary">
          <div>签核单：<strong>{{ confirmRow.签核单编号 }}</strong>（id={{ confirmRow.id }}）</div>
          <div>快照：{{ confirmRow.快照编号 }} · 签核修订
            <strong data-testid="confirm-revision">{{ confirmRow.修订号 }}</strong>
            · 摘要 {{ confirmRow.快照摘要值 }}
          </div>
          <div>制单人：<strong>{{ confirmRow.制单人 }}</strong></div>
        </div>

        <label class="create-field">
          <span>签核人（必须是另一位操作员）</span>
          <input
            id="confirm-signer"
            v-model="confirmForm.signer"
            data-testid="confirm-签核人"
            list="operator-options"
            placeholder="填写与制单人不同的操作员"
            required
          />
        </label>
        <p v-if="sameOperatorHint" class="error-text" data-testid="same-operator-hint">
          制单人与签核人属于同一人「{{ confirmRow.制单人 }}」，提交后将被拒绝受理，请更换操作员。
        </p>
        <label class="create-field">
          <span>签核结论</span>
          <select v-model="confirmForm.conclusion" data-testid="confirm-签核结论">
            <option value="通过">通过（同意，可用于发布开单）</option>
            <option value="驳回">驳回</option>
          </select>
        </label>
        <label class="create-field">
          <span>签核意见</span>
          <textarea
            v-model="confirmForm.opinion"
            data-testid="confirm-签核意见"
            rows="3"
            placeholder="核对行数、摘要与修订是否一致"
          ></textarea>
        </label>

        <p v-if="confirmError" class="error-text" data-testid="confirm-error" role="alert">{{ confirmError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" @click="confirmRow = null">取消</button>
          <button class="btn" type="button" data-testid="submit-reject" :disabled="submitting" @click="submitReject">
            驳回
          </button>
          <button class="btn primary" data-testid="submit-confirm-sign" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认签核并提交' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 撤回弹窗：并行场景下与发布开单同时提交 -->
    <div v-if="withdrawRow" class="modal-backdrop" data-testid="withdraw-modal" role="dialog" aria-modal="true" aria-label="撤回快照签核单">
      <form class="modal" @submit.prevent="submitWithdraw">
        <h3>撤回快照签核单</h3>
        <div class="confirm-summary">
          <div>签核单：<strong>{{ withdrawRow.签核单编号 }}</strong>（id={{ withdrawRow.id }}）</div>
          <div>当前状态：{{ withdrawRow.status }} · 修订 {{ withdrawRow.修订号 }}</div>
          <p class="warn-text">
            撤回后该签核单立即不可用于发布开单；若发布开单已抢先写入申请，本次撤回会收到冲突拒绝。
          </p>
        </div>
        <label class="create-field">
          <span>撤回人</span>
          <input
            v-model="withdrawForm.operator"
            data-testid="withdraw-撤回人"
            list="operator-options"
            placeholder="撤回操作人"
          />
        </label>
        <label class="create-field">
          <span>撤回原因</span>
          <textarea
            v-model="withdrawForm.reason"
            data-testid="withdraw-撤回原因"
            rows="3"
            placeholder="例如：快照内容需要补改"
          ></textarea>
        </label>
        <p v-if="withdrawError" class="error-text" data-testid="withdraw-error" role="alert">{{ withdrawError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" @click="withdrawRow = null">取消</button>
          <button class="btn primary danger-btn" data-testid="submit-withdraw" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认撤回并提交' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 供 create 表单引用的候选列表 -->
    <datalist id="snapshot-options">
      <option v-for="snap in snapshots" :key="snap.id" :value="String(snap.快照编号)">
        {{ snap.所属维度 }} · 当前修订 {{ snap.修订号 || 'R1' }} · 摘要 {{ snap.快照摘要值 }}
      </option>
    </datalist>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  confirmSignoff,
  createEntry,
  downloadEntries,
  listEntries,
  runAction,
  withdrawSignoff,
} from '@/api/backend-service'
import { useOperator } from '@/composables/useOperator'
import { moduleMeta } from '@/data/modules'
import type { EntryRow } from '@/data/types'

const route = useRoute()
const router = useRouter()
const meta = moduleMeta('snapshot_signoff')
const { currentOperator } = useOperator()

const rows = ref<EntryRow[]>([])
const snapshots = ref<EntryRow[]>([])
const errorMessage = ref('')
const highlightId = ref<number | null>(null)
// 与通用工作台一致：前三个字段作为筛选字段
const filterFields = meta.fields.slice(0, 3)
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const banner = reactive<{ kind: 'ok' | 'err'; message: string }>({ kind: 'ok', message: '' })

const showCreate = ref(false)
const submitting = ref(false)
const createValues = ref<Record<string, string>>({})
const createRemark = ref('')
const createError = ref('')

const confirmRow = ref<EntryRow | null>(null)
const confirmForm = reactive({ signer: '', conclusion: '通过', opinion: '' })
const confirmError = ref('')

const withdrawRow = ref<EntryRow | null>(null)
const withdrawForm = reactive({ operator: '', reason: '' })
const withdrawError = ref('')

const filteredRows = computed(() => {
  return rows.value.filter((row) => {
    if (statusFilter.value && row.status !== statusFilter.value) return false
    for (const [field, keyword] of Object.entries(filters.value)) {
      const kw = keyword?.trim()
      if (kw && !String(row[field] ?? '').includes(kw)) return false
    }
    return true
  })
})

const pagedRows = computed(() => filteredRows.value.slice(0, 200))

const stats = computed(() => [
  { key: 'total', label: meta.metrics[0], value: rows.value.length },
  { key: 'pending', label: '待另一位操作员签核', value: rows.value.filter((r) => r.status === '待签核').length },
  { key: 'usable', label: '有效可开单', value: rows.value.filter((r) => r.usable === true).length },
])

const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

const matchedSnapshot = computed(() => {
  const key = createValues.value['快照编号']?.trim()
  if (!key) return null
  return snapshots.value.find((s) => String(s.快照编号) === key || String(s.id) === key) ?? null
})

const sameOperatorHint = computed(() => {
  if (!confirmRow.value) return false
  const signer = confirmForm.signer.trim()
  return !!signer && signer === String(confirmRow.value.制单人 ?? '').trim()
})

const anyModal = computed(() => showCreate.value || confirmRow.value !== null || withdrawRow.value !== null)

function isRequired(field: string): boolean {
  return !!meta.requiredFields?.includes(field)
}

function listForField(field: string): string | undefined {
  if (field === '快照编号') return 'snapshot-options'
  if (field === '制单人' || field === '签核人' || field === '撤回人') return 'operator-options'
  return undefined
}

function placeholderFor(field: string): string {
  if (field === '快照编号') return '例如 SNAP-CUST-20261001'
  if (field === '制单人') return '制单操作员标识'
  return ''
}

function statusClass(status: string): string {
  return `st-${status}`
}

function showBanner(kind: 'ok' | 'err', message: string) {
  banner.kind = kind
  banner.message = message
}

async function reload() {
  errorMessage.value = ''
  try {
    const [signoffPage, snapshotPage] = await Promise.all([
      listEntries('snapshot_signoff', { size: '200' }),
      listEntries('dim_snapshot', { size: '200' }),
    ])
    rows.value = signoffPage.items
    snapshots.value = snapshotPage.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '签核单读取失败'
  }
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
}

async function exportRows() {
  try {
    await downloadEntries('snapshot_signoff')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function snapshotRefFromQuery(): string {
  const q = route.query.newFor ?? route.query.snapshotId ?? route.query.snapshot
  if (q === undefined) return ''
  return String(Array.isArray(q) ? q[0] : q)
}

function openCreate(sourceRow?: EntryRow) {
  createError.value = ''
  createRemark.value = ''
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  let snapshotNo = ''
  if (sourceRow) {
    snapshotNo = String(sourceRow.快照编号 ?? '')
  } else {
    const ref = snapshotRefFromQuery()
    if (ref) {
      const snap = snapshots.value.find((s) => String(s.id) === ref || String(s.快照编号) === ref)
      snapshotNo = snap ? String(snap.快照编号) : ref
    }
  }
  createValues.value['快照编号'] = snapshotNo
  createValues.value['制单人'] = currentOperator.value
  showCreate.value = true
}

async function submitCreate() {
  createError.value = ''
  if (!createValues.value['快照编号']?.trim()) {
    createError.value = '请选择维度快照'
    return
  }
  if (!createValues.value['制单人']?.trim()) {
    createError.value = '请填写制单人'
    return
  }
  submitting.value = true
  try {
    // 走通用资源登记约定（POST /api/snapshot_signoff），后端分派到制单提交
    const result = await createEntry('snapshot_signoff', {
      ...createValues.value,
      制单说明: createRemark.value,
    })
    if (!result.ok) {
      createError.value = result.message
      showBanner('err', result.message)
      return
    }
    showCreate.value = false
    showBanner('ok', result.message)
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '制单提交失败'
  } finally {
    submitting.value = false
  }
}

function openConfirm(row: EntryRow) {
  confirmRow.value = row
  confirmError.value = ''
  confirmForm.signer = currentOperator.value
  confirmForm.conclusion = '通过'
  confirmForm.opinion = ''
}

async function submitConfirm() {
  if (!confirmRow.value) return
  confirmError.value = ''
  if (!confirmForm.signer.trim()) {
    confirmError.value = '请填写签核人（另一位操作员）'
    return
  }
  submitting.value = true
  try {
    // 即使前端已提示同一人，仍提交给后端做权威裁决（拒绝受理）
    const result = await confirmSignoff(confirmRow.value.id, {
      签核人: confirmForm.signer.trim(),
      签核结论: confirmForm.conclusion,
      签核意见: confirmForm.opinion.trim(),
    })
    if (!result.ok) {
      confirmError.value = result.message
      showBanner('err', result.message)
      await reload()
      const fresh = rows.value.find((r) => r.id === confirmRow.value?.id)
      if (fresh) confirmRow.value = fresh
      return
    }
    confirmRow.value = null
    showBanner('ok', result.message)
    await reload()
  } catch (error) {
    confirmError.value = error instanceof Error ? error.message : '签核提交失败'
  } finally {
    submitting.value = false
  }
}

async function submitReject() {
  if (!confirmRow.value) return
  if (!confirmForm.signer.trim()) {
    confirmError.value = '请填写签核人'
    return
  }
  submitting.value = true
  try {
    const result = await runAction('snapshot_signoff', confirmRow.value.id, '驳回', {
      operator: confirmForm.signer.trim(),
      签核人: confirmForm.signer.trim(),
      签核意见: confirmForm.opinion.trim(),
    })
    if (!result.ok) {
      confirmError.value = result.message
      showBanner('err', result.message)
      return
    }
    confirmRow.value = null
    showBanner('ok', result.message)
    await reload()
  } catch (error) {
    confirmError.value = error instanceof Error ? error.message : '驳回失败'
  } finally {
    submitting.value = false
  }
}

function openWithdraw(row: EntryRow) {
  withdrawRow.value = row
  withdrawError.value = ''
  withdrawForm.operator = currentOperator.value
  withdrawForm.reason = ''
}

async function submitWithdraw() {
  if (!withdrawRow.value) return
  withdrawError.value = ''
  submitting.value = true
  const targetId = withdrawRow.value.id
  try {
    const result = await withdrawSignoff(targetId, {
      撤回人: withdrawForm.operator.trim() || currentOperator.value,
      撤回原因: withdrawForm.reason.trim(),
    })
    if (!result.ok) {
      // 并发冲突：保留弹窗并展示后端最新状态，同时刷新列表
      withdrawError.value = result.message
      showBanner('err', result.message)
      await reload()
      const fresh = rows.value.find((r) => r.id === targetId)
      if (fresh) withdrawRow.value = fresh
      return
    }
    withdrawRow.value = null
    showBanner('ok', result.message)
    await reload()
  } catch (error) {
    withdrawError.value = error instanceof Error ? error.message : '撤回失败'
  } finally {
    submitting.value = false
  }
}

function goPublish(row: EntryRow) {
  void router.push({ path: '/dim_publish', query: { signoff: String(row.id) } })
}

function onVisibility() {
  if (document.visibilityState === 'visible') void reload()
}

watch(
  () => route.query,
  () => {
    const hl = route.query.signoff ?? route.query.id
    if (hl) highlightId.value = Number(hl)
    if (route.query.newFor !== undefined) {
      void reload().then(() => openCreate())
    }
  },
)

onMounted(async () => {
  await reload()
  const hl = route.query.signoff ?? route.query.id
  if (hl) highlightId.value = Number(hl)
  if (route.query.newFor !== undefined || route.query.action === 'new') {
    openCreate()
  }
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; }
.flow-banner { display: flex; justify-content: space-between; gap: 12px; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.flow-banner.ok { background: #ecfdf3; border: 1px solid #6ce9a6; color: #067647; }
.flow-banner.err { background: #fef3f2; border: 1px solid #fda29b; color: #b42318; }
.data-table { background: #fff; }
.strong { font-weight: 600; }
.small { font-size: 12px; }
.muted { color: var(--muted); }
.error-text { color: #b42318; }
.next-step { max-width: 260px; font-size: 12px; color: #334155; }
.row-actions.wrap { flex-wrap: wrap; row-gap: 4px; }
.alias-hook { display: inline; }
.link.danger { color: #b42318; }
.btn.danger-btn { background: #d92d20; border-color: #d92d20; color: #fff; }
.status-badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #eef2f6; }
.st-待签核 { background: #fffaeb; color: #b54708; }
.st-已签核 { background: #ecfdf3; color: #067647; }
.st-已使用 { background: #eff8ff; color: #175cd3; }
.st-已撤回 { background: #f2f4f7; color: #475467; }
.st-已失效, .st-已驳回 { background: #fef3f2; color: #b42318; }
.usable-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.usable-badge.ok { background: #ecfdf3; color: #067647; }
.usable-badge.bad { background: #fef3f2; color: #b42318; }
.rev-tag { display: inline-block; background: #eef4ff; color: #1f6feb; border-radius: 4px; padding: 0 6px; margin-right: 6px; font-size: 12px; }
.highlight { outline: 2px solid #1f6feb; }
.snapshot-hint, .confirm-summary { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px; display: grid; gap: 4px; }
.warn-text { color: #b54708; font-size: 12px; margin: 4px 0 0; }
.create-field textarea, .create-field input, .create-field select { width: 100%; box-sizing: border-box; border: 1px solid var(--border); border-radius: 6px; padding: 8px; font-family: inherit; }
</style>
