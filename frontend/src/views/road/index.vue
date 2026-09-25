<template>
  <section class="page" data-module="road">
    <header class="page-head">
      <div>
        <h2>道路设施管理</h2>
        <p class="page-desc">维护道路设施，围绕设施编码、道路名称、道路等级、起止桩号做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记道路设施</button>
        <button class="btn" type="button" @click="exportRows">导出道路设施清单</button>
      </div>
    </header>

    <div class="view-tabs" role="tablist" aria-label="道路设施视图切换">
      <button
        type="button"
        role="tab"
        :class="['tab-button', { active: viewMode === 'ledger' }]"
        :aria-selected="viewMode === 'ledger'"
        @click="switchView('ledger')"
      >
        道路台账
      </button>
      <button
        type="button"
        role="tab"
        :class="['tab-button', { active: viewMode === 'overview' }]"
        :aria-selected="viewMode === 'overview'"
        @click="switchView('overview')"
      >
        路况总览
      </button>
    </div>

    <div v-if="viewMode === 'ledger'">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reloadLedger">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ display(row[column]) }}</td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length && !ledgerLoading">
            <td :colspan="columns.length + 1" class="empty-state">
              <div>暂无道路设施数据，可先登记道路设施</div>
              <button class="btn" type="button" @click="reloadLedger">刷新列表</button>
            </td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条道路设施记录</span>
        <span v-if="ledgerErrorMessage" class="error-text">{{ ledgerErrorMessage }}</span>
      </footer>
    </div>

    <div v-else class="condition-overview">
      <div class="overview-toolbar">
        <div>
          <h3>路况总览</h3>
          <p>按道路等级与管养单位成排汇总最近登记病害、未闭环养护计划和施工进度。</p>
        </div>
        <button class="btn" type="button" :disabled="overviewLoading" @click="loadOverview">
          {{ overviewLoading ? '刷新中...' : '刷新总览' }}
        </button>
      </div>

      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">视图设施合计</span>
          <strong class="stat-value">{{ overview?.total ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">台账设施合计</span>
          <strong class="stat-value">{{ total }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">登记病害</span>
          <strong class="stat-value">{{ overview?.disease_total ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">未闭环计划</span>
          <strong class="stat-value">{{ overview?.open_plan_count ?? 0 }}</strong>
        </article>
      </div>

      <div v-if="overviewErrorMessage" class="panel empty-panel">
        <strong>路况总览暂时读取失败</strong>
        <p>{{ overviewErrorMessage }}</p>
        <button class="btn primary" type="button" @click="loadOverview">重新加载</button>
      </div>

      <div v-else-if="!overviewLoading && overview && overview.total === 0" class="panel empty-panel">
        <strong>暂无道路设施</strong>
        <p>当前片区还没有道路设施台账，登记后即可在总览中查看病害和养护计划。</p>
        <div class="empty-actions">
          <button class="btn primary" type="button" @click="openCreate">登记道路设施</button>
          <button class="btn" type="button" @click="loadOverview">刷新</button>
        </div>
      </div>

      <template v-else-if="overview">
        <div v-if="overview.disease_total === 0" class="panel disease-empty-panel">
          <div>
            <strong>本片区暂未登记病害</strong>
            <p>道路设施已展示，但病害数量为 0；登记病害并关联道路后，这里会显示最新路况。</p>
          </div>
          <button class="btn" type="button" @click="loadOverview">刷新病害数据</button>
        </div>

        <div v-if="overviewLoading && !overview.groups.length" class="panel empty-panel">正在加载路况总览...</div>

        <div v-for="group in overview.groups" :key="`${group.road_level}-${group.maintenance_unit}`" class="group-row">
          <div class="group-head">
            <div>
              <strong>{{ group.road_level }}</strong>
              <span>{{ group.maintenance_unit }}</span>
            </div>
            <p>{{ group.count }} 条设施 · {{ group.disease_count }} 条病害 · {{ group.open_plan_count }} 个未闭环计划</p>
          </div>
          <div class="card-grid">
            <button
              v-for="item in group.items"
              :key="String(item.id)"
              type="button"
              :class="['condition-card', { selected: selectedId === item.id }]"
              @click="openDetail(item.id)"
            >
              <span class="card-status">{{ item.status }}</span>
              <strong class="card-title">{{ item.road_name }}</strong>
              <span class="card-code">{{ item.road_code }}</span>
              <div class="metric-line">
                <span><b>{{ item.disease_count }}</b> 条病害</span>
                <span><b>{{ item.open_plan_count }}</b> 个未闭环计划</span>
              </div>
              <small v-if="item.latest_disease_date">
                最近登记：{{ item.latest_disease_date }} · {{ item.latest_disease_type || '病害' }}
              </small>
              <small v-else>最近登记：暂无病害</small>
            </button>
          </div>
        </div>

        <aside class="detail-panel" aria-live="polite">
          <div v-if="detailLoading" class="panel empty-panel">正在读取道路明细...</div>

          <div v-else-if="!detail" class="panel empty-panel">
            <strong>请选择一条道路设施</strong>
            <p>点开上方任意道路卡片，可查看关联病害、养护计划与施工进度。</p>
          </div>

          <div v-else>
            <div class="detail-head">
              <div>
                <h3>{{ detail.road['道路名称'] }}</h3>
                <p>{{ detail.road['设施编码'] }} · {{ detail.road['道路等级'] }} · {{ detail.road['管养单位'] || '未分配单位' }}</p>
              </div>
              <button class="btn" type="button" @click="openEdit(detail.road)">修改设施</button>
            </div>

            <div class="detail-summary">
              <span><b>{{ detail.disease_count }}</b> 关联病害</span>
              <span><b>{{ detail.open_plan_count }}</b> 未闭环计划</span>
              <span>状态：{{ display(detail.road.status) }}</span>
            </div>

            <section class="detail-section">
              <div class="section-title">
                <h4>关联病害</h4>
                <span>{{ detail.diseases.length }} 条</span>
              </div>
              <table v-if="detail.diseases.length" class="data-table compact-table">
                <thead>
                  <tr>
                    <th>病害编号</th>
                    <th>类型</th>
                    <th>位置</th>
                    <th>等级</th>
                    <th>发现日期</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="disease in detail.diseases" :key="String(disease.id)">
                    <td>{{ display(disease['病害编号']) }}</td>
                    <td>{{ display(disease['病害类型']) }}</td>
                    <td>{{ display(disease['病害位置']) }}</td>
                    <td>{{ display(disease['严重等级']) }}</td>
                    <td>{{ display(disease['发现日期']) }}</td>
                    <td>{{ display(disease.status) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="sub-empty">该道路暂未登记病害。</div>
            </section>

            <section class="detail-section">
              <div class="section-title">
                <h4>养护计划与施工进度</h4>
                <span>{{ detail.plans.length }} 个计划</span>
              </div>
              <div v-if="detail.plans.length" class="plan-list">
                <article v-for="item in detail.plans" :key="String(item.plan.id)" class="plan-card">
                  <div class="plan-head">
                    <div>
                      <strong>{{ display(item.plan['计划编号']) }} · {{ display(item.plan['养护类型']) }}</strong>
                      <p>{{ display(item.plan['计划工期']) }}</p>
                    </div>
                    <span class="plan-status">{{ display(item.plan.status) }}</span>
                  </div>
                  <div class="progress-track">
                    <span :style="{ width: `${item.progress.percent}%` }"></span>
                  </div>
                  <div class="progress-meta">
                    <span>{{ item.progress.status }} · {{ item.progress.percent }}%</span>
                    <span>{{ item.work_count }} 个施工任务，{{ item.progress.completed_count }} 个已完工</span>
                  </div>
                  <ul v-if="item.works.length" class="work-list">
                    <li v-for="work in item.works" :key="String(work.id)">
                      {{ display(work['施工编号']) }}｜{{ display(work['承接单位']) }}｜{{ display(work.status) }}
                    </li>
                  </ul>
                  <div v-else class="sub-empty">该计划尚未生成施工任务。</div>
                </article>
              </div>
              <div v-else class="sub-empty">该道路暂无养护计划。</div>
            </section>
          </div>
        </aside>
      </template>
    </div>

    <div v-if="formOpen" class="modal-mask" @click.self="closeForm">
      <form class="modal-panel" @submit.prevent="submitForm">
        <div class="modal-head">
          <h3>{{ formMode === 'create' ? '登记道路设施' : '修改道路设施' }}</h3>
          <button type="button" class="link" @click="closeForm">关闭</button>
        </div>
        <div class="form-grid">
          <label v-for="field in formFields" :key="field" :class="{ required: requiredFields.includes(field) }">
            <span>{{ field }}</span>
            <input v-model="formValues[field]" :placeholder="`请输入${field}`" />
          </label>
        </div>
        <p v-if="formErrorMessage" class="error-text">{{ formErrorMessage }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="closeForm">取消</button>
          <button type="submit" class="btn primary" :disabled="formSaving">
            {{ formSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type ViewMode = 'ledger' | 'overview'
type FormMode = 'create' | 'edit'

interface RoadItem {
  id: number
  road_code: string
  road_name: string
  road_level: string
  maintenance_unit: string
  status: string
  disease_count: number
  open_plan_count: number
  latest_disease_date: string | null
  latest_disease_type: string | null
}

interface RoadGroup {
  road_level: string
  maintenance_unit: string
  count: number
  disease_count: number
  open_plan_count: number
  latest_disease_date: string | null
  items: RoadItem[]
}

interface RoadOverview {
  total: number
  disease_total: number
  disease_count: number
  open_plan_count: number
  groups: RoadGroup[]
}

interface PlanProgress {
  percent: number
  status: string
  completed_count: number
}

interface PlanLink {
  plan: Row
  works: Row[]
  work_count: number
  progress: PlanProgress
}

interface RoadDetail {
  road: Row
  diseases: Row[]
  plans: PlanLink[]
  disease_count: number
  open_plan_count: number
}

const ENDPOINT = '/api/road'
const VIEW_STORAGE_KEY = 'road-condition-view-state'
const columns = ['设施编码', '道路名称', '道路等级', '起止桩号', '路面结构', '管养单位', '建成年份', '设施状态']
const actions = ['办理移交', '标记观测', '封闭设施']
const filterFields = ['设施编码', '道路名称', '道路等级', '管养单位']
const formFields = ['设施编码', '道路名称', '道路等级', '起止桩号', '路面结构', '管养单位', '建成年份']
const requiredFields = ['设施编码', '道路名称', '道路等级']

const rows = ref<Row[]>([])
const total = ref(0)
const ledgerLoading = ref(false)
const ledgerErrorMessage = ref('')
const filters = ref<Record<string, string>>({})

const viewMode = ref<ViewMode>('ledger')
const overview = ref<RoadOverview | null>(null)
const overviewLoading = ref(false)
const overviewErrorMessage = ref('')
const selectedId = ref<number | null>(null)
const detail = ref<RoadDetail | null>(null)
const detailLoading = ref(false)

const formOpen = ref(false)
const formMode = ref<FormMode>('create')
const formSaving = ref(false)
const formErrorMessage = ref('')
const editingId = ref<number | null>(null)
const formValues = ref<Record<string, string>>({})

const stats = computed(() => [
  { label: '在养道路', value: rows.value.filter((row) => ['正常养护', '重点观测'].includes(String(row.status))).length },
  { label: '重点观测道路', value: rows.value.filter((row) => String(row.status) === '重点观测').length },
  { label: '道路设施合计', value: total.value },
])

function display(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function persistViewState() {
  sessionStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify({
    viewMode: viewMode.value,
    selectedId: selectedId.value,
  }))
}

function restoreViewState() {
  try {
    const raw = sessionStorage.getItem(VIEW_STORAGE_KEY)
    if (!raw) return
    const state = JSON.parse(raw) as { viewMode?: ViewMode; selectedId?: number | null }
    if (state.viewMode === 'overview' || state.viewMode === 'ledger') {
      viewMode.value = state.viewMode
    }
    if (typeof state.selectedId === 'number') {
      selectedId.value = state.selectedId
    }
  } catch {
    sessionStorage.removeItem(VIEW_STORAGE_KEY)
  }
}

function resetFilters() {
  filters.value = {}
  void reloadLedger()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reloadLedger() {
  ledgerLoading.value = true
  ledgerErrorMessage.value = ''
  const query = new URLSearchParams()
  const queryMap: Record<string, string> = {
    设施编码: 'keyword',
    道路名称: 'name',
    道路等级: 'level',
    管养单位: 'unit',
  }
  Object.entries(filters.value).forEach(([field, value]) => {
    const trimmed = value.trim()
    const queryName = queryMap[field]
    if (trimmed && queryName) {
      query.set(queryName, trimmed)
    }
  })
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('道路设施列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    ledgerErrorMessage.value = error instanceof Error ? error.message : '道路设施列表读取失败'
  } finally {
    ledgerLoading.value = false
  }
}

async function runAction(action: string, row: Row) {
  ledgerErrorMessage.value = ''
  filters.value = {}
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('道路设施动作未生效，请稍后重试')
    }
    await Promise.all([reloadLedger(), syncOverviewAfterChange()])
  } catch (error) {
    ledgerErrorMessage.value = error instanceof Error ? error.message : '道路设施操作失败'
  }
}

async function loadOverview() {
  overviewLoading.value = true
  overviewErrorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/overview`)
    if (!response.ok) {
      throw new Error('路况总览读取失败')
    }
    const payload: RoadOverview = await response.json()
    overview.value = payload
    const selectedExists = payload.groups.some((group) => group.items.some((item) => item.id === selectedId.value))
    if (!selectedExists) {
      selectedId.value = null
      detail.value = null
    } else if (selectedId.value !== null) {
      await loadDetail(selectedId.value)
    }
  } catch (error) {
    overviewErrorMessage.value = error instanceof Error ? error.message : '路况总览读取失败'
  } finally {
    overviewLoading.value = false
  }
}

async function syncOverviewAfterChange() {
  if (viewMode.value !== 'overview' || !overview.value) return
  await loadOverview()
}

async function loadDetail(id: number) {
  detailLoading.value = true
  try {
    const response = await request(`${ENDPOINT}/${id}/condition`)
    if (response.status === 404) {
      selectedId.value = null
      detail.value = null
      persistViewState()
      return
    }
    if (!response.ok) {
      throw new Error('道路关联信息读取失败')
    }
    detail.value = await response.json()
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

async function openDetail(id: number) {
  selectedId.value = id
  persistViewState()
  await loadDetail(id)
}

async function switchView(mode: ViewMode) {
  viewMode.value = mode
  persistViewState()
  if (mode === 'overview') {
    await loadOverview()
  } else {
    await reloadLedger()
  }
}

function blankForm() {
  return Object.fromEntries(formFields.map((field) => [field, '']))
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  formValues.value = blankForm()
  formErrorMessage.value = ''
  formOpen.value = true
}

function openEdit(road: Row) {
  formMode.value = 'edit'
  editingId.value = Number(road.id)
  formValues.value = Object.fromEntries(formFields.map((field) => [field, String(road[field] ?? '')]))
  formErrorMessage.value = ''
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  formSaving.value = false
  formErrorMessage.value = ''
}

async function submitForm() {
  const missing = requiredFields.filter((field) => !formValues.value[field]?.trim())
  if (missing.length) {
    formErrorMessage.value = `请填写必填字段：${missing.join('、')}`
    return
  }
  formSaving.value = true
  formErrorMessage.value = ''
  const values = Object.fromEntries(Object.entries(formValues.value).map(([key, value]) => [key, value.trim()]))
  try {
    const url = formMode.value === 'create' ? ENDPOINT : `${ENDPOINT}/${editingId.value}`
    const response = await request(url, {
      method: formMode.value === 'create' ? 'POST' : 'PATCH',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.detail?.[0]?.msg || payload?.message || '道路设施保存失败')
    }
    closeForm()
    filters.value = {}
    await Promise.all([reloadLedger(), loadOverview()])
  } catch (error) {
    formErrorMessage.value = error instanceof Error ? error.message : '道路设施保存失败'
  } finally {
    formSaving.value = false
  }
}

onMounted(async () => {
  restoreViewState()
  await Promise.all([
    reloadLedger(),
    viewMode.value === 'overview' ? loadOverview() : Promise.resolve(),
  ])
})
</script>

<style scoped>
.view-tabs {
  display: flex;
  gap: 8px;
  margin: 0 0 12px;
}

.tab-button {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px 8px 0 0;
  padding: 8px 18px;
  cursor: pointer;
}

.tab-button.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}

.overview-toolbar,
.detail-head,
.plan-head,
.group-head,
.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.overview-toolbar {
  align-items: center;
  margin-bottom: 12px;
}

.overview-toolbar h3,
.detail-head h3 {
  margin: 0 0 4px;
}

.overview-toolbar p,
.detail-head p,
.plan-head p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.empty-panel {
  text-align: center;
  color: var(--muted);
  line-height: 1.8;
}

.empty-panel .btn {
  margin-top: 8px;
}

.empty-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.disease-empty-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-align: left;
  margin-bottom: 12px;
  border-color: #f4d35e;
  background: #fffbeb;
}

.disease-empty-panel p {
  margin: 4px 0 0;
}

.group-row {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}

.group-head {
  align-items: baseline;
  border-bottom: 1px solid #edf1f5;
  padding-bottom: 8px;
  margin-bottom: 10px;
}

.group-head strong {
  margin-right: 8px;
}

.group-head span,
.group-head p {
  color: var(--muted);
  font-size: 12px;
}

.group-head p {
  margin: 0;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}

.condition-card {
  position: relative;
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fbfdff;
  padding: 12px;
  cursor: pointer;
  min-height: 142px;
}

.condition-card:hover,
.condition-card.selected {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.12);
}

.card-status {
  display: inline-block;
  color: var(--brand);
  background: #eaf2ff;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
}

.card-title {
  display: block;
  margin-top: 8px;
  font-size: 16px;
}

.card-code,
.condition-card small {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}

.metric-line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin: 12px 0 8px;
  font-size: 12px;
}

.metric-line b {
  font-size: 18px;
  color: #b42318;
}

.metric-line span:last-child b {
  color: #b54708;
}

.detail-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}

.detail-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 10px 0 14px;
  font-size: 13px;
}

.detail-summary b {
  font-size: 18px;
  color: var(--brand);
}

.detail-section {
  margin-top: 14px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-title h4 {
  margin: 0;
}

.section-title span {
  color: var(--muted);
  font-size: 12px;
}

.compact-table th,
.compact-table td {
  padding: 6px 8px;
  font-size: 12px;
}

.sub-empty {
  border: 1px dashed var(--border);
  border-radius: 6px;
  color: var(--muted);
  padding: 10px;
  font-size: 12px;
  text-align: center;
}

.plan-list {
  display: grid;
  gap: 10px;
}

.plan-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
}

.plan-status {
  color: #b54708;
  font-size: 12px;
  white-space: nowrap;
}

.progress-track {
  height: 8px;
  background: #edf1f5;
  border-radius: 999px;
  overflow: hidden;
  margin: 10px 0 6px;
}

.progress-track span {
  display: block;
  height: 100%;
  background: var(--brand);
  border-radius: inherit;
}

.progress-meta {
  color: var(--muted);
  font-size: 12px;
}

.work-list {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #475569;
  font-size: 12px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

.modal-panel {
  width: min(760px, calc(100vw - 32px));
  background: #fff;
  border-radius: 10px;
  padding: 16px;
}

.modal-head,
.modal-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.modal-head h3 {
  margin: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.form-grid label span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}

.form-grid label.required span::after {
  content: ' *';
  color: #b42318;
}

.form-grid input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 9px;
}

.modal-actions {
  justify-content: flex-end;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .overview-toolbar,
  .disease-empty-panel,
  .group-head,
  .detail-head,
  .plan-head,
  .progress-meta {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
