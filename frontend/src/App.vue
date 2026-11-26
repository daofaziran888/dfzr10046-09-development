<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">维链工坊 · 维度建模与缓慢变化维加工平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向维度注册、缓慢变化维拉链、一致性维度核对、事实表装配、代理键生成、维度退化、迟到事实回补、汇总层派生、指标口径绑定与维度快照发布的数仓维度建模加工平台。</span>
        <div class="operator-bar" data-testid="operator-bar">
          <label class="operator-label" for="current-operator">当前操作员</label>
          <input
            id="current-operator"
            name="operator"
            aria-label="当前操作员"
            data-testid="current-operator"
            class="operator-input"
            list="operator-options"
            :value="currentOperator"
            placeholder="填写姓名/工号"
            @input="onOperatorInput"
          />
          <datalist id="operator-options">
            <option value="张三"></option>
            <option value="李四"></option>
            <option value="王五"></option>
            <option value="赵六"></option>
          </datalist>
          <span class="operator-hint">制单与签核须为不同人</span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useOperator } from '@/composables/useOperator'

const { currentOperator, setOperator } = useOperator()

function onOperatorInput(event: Event) {
  setOperator((event.target as HTMLInputElement).value)
}

const navItems = [{ label: "运营概览", path: "/" }, { label: "维度建档", path: "/dim_entry" }, { label: "拉链加工", path: "/scd_chain" }, { label: "代理键生成", path: "/surrogate_key" }, { label: "一致性核对", path: "/conform_check" }, { label: "事实装配", path: "/fact_assemble" }, { label: "退化维度", path: "/degenerate_dim" }, { label: "迟到事实", path: "/late_fact" }, { label: "汇总层派生", path: "/summary_layer" }, { label: "粒度声明", path: "/grain_declare" }, { label: "度量目录", path: "/measure_catalog" }, { label: "指标绑定", path: "/metric_bind" }, { label: "维度快照", path: "/dim_snapshot" }, { label: "快照签核单", path: "/snapshot_signoff" }, { label: "层级路径", path: "/hier_path" }, { label: "多值桥接", path: "/bridge_link" }, { label: "属性失效", path: "/attr_decay" }, { label: "装载窗口", path: "/load_window" }, { label: "重跑任务", path: "/reprocess_task" }, { label: "装配质量闸", path: "/quality_gate" }, { label: "血缘关系", path: "/lineage_edge" }, { label: "维度发布", path: "/dim_publish" }, { label: "建模审计", path: "/model_audit" }, { label: "源端抽取", path: "/src_extract" }]
</script>

<style scoped>
.operator-bar { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.operator-label { font-size: 12px; color: var(--muted); white-space: nowrap; }
.operator-input { width: 170px; padding: 5px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
.operator-hint { font-size: 12px; color: #b45309; white-space: nowrap; }
</style>
