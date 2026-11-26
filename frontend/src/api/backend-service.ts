import { request } from './client'
import { operatorHeaders, operatorName } from '@/composables/useOperator'
import { moduleMeta } from '@/data/modules'
import type { ActionResult, EntryRow, OverviewResult, PageResult } from '@/data/types'

export { moduleMeta }

function headers(extra?: Record<string, string>): Record<string, string> {
  return { ...operatorHeaders(), ...(extra ?? {}) }
}

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function getEntry(key: string, id: number | string): Promise<EntryRow> {
  const response = await request(`/api/${key}/${id}`)
  if (!response.ok) throw new Error('单据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ values, operator: operatorName() }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
  extra: Record<string, unknown> = {},
): Promise<ActionResult> {
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      action,
      operator: operatorName(),
      ...extra,
    }),
  })
  return await response.json()
}

// ---------------- 快照签核单专用接口 ----------------

export async function submitSignoff(
  values: Record<string, unknown>,
): Promise<ActionResult> {
  const response = await request('/api/snapshot_signoff/submit', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      operator: operatorName(),
      ...values,
    }),
  })
  return await response.json()
}

export async function confirmSignoff(
  id: number | string,
  payload: Record<string, unknown>,
): Promise<ActionResult> {
  const response = await request(`/api/snapshot_signoff/${id}/confirm`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      operator: operatorName(),
      ...payload,
    }),
  })
  return await response.json()
}

export async function withdrawSignoff(
  id: number | string,
  payload: Record<string, unknown> = {},
): Promise<ActionResult> {
  const response = await request(`/api/snapshot_signoff/${id}/withdraw`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      operator: operatorName(),
      ...payload,
    }),
  })
  return await response.json()
}

export async function signoffUsability(
  id: number | string,
): Promise<{ usable: boolean; code: string; reason: string; status?: string; next_step?: string }> {
  const response = await request(`/api/snapshot_signoff/${id}/usability`)
  return await response.json()
}

// ---------------- 维度发布凭单开单 ----------------

export async function applyPublish(
  payload: Record<string, unknown>,
): Promise<ActionResult> {
  const response = await request('/api/dim_publish/apply', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      operator: operatorName(),
      ...payload,
    }),
  })
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}
