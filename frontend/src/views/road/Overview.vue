<template>
  <section class="page" data-module="road-overview">
    <header class="page-head">
      <div>
        <h2>道路设施路况总览</h2>
        <p class="page-desc">
          道路设施按道路等级与管养单位分组成排展示，每格汇总最近 {{ recentDays }} 天登记的病害数与尚未闭环的养护计划数；
          点开单条可查看关联病害与施工进度，改级改单位直接落在台账同一条记录上。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" :disabled="loading" @click="reload()">刷新总览</button>
        <RouterLink class="btn" to="/road">前往道路设施台账</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in inViewStats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
      <button class="link" type="button" @click="reload()">点此重试</button>
    </p>

    <!-- 全局空态：一条道路设施都没有（加载失败时不与错误横幅重复出现） -->
    <div v-if="!loading && !errorMessage && !groups.length" class="overview-empty">
      <p class="empty-title">暂无道路设施</p>
      <p class="empty-desc">台账里还没有任何道路设施，总览无法分组。先在台账登记道路设施后，再回到这里刷新。</p>
      <div class="empty-actions">
        <button class="btn primary" type="button" @click="reload()">刷新总览</button>
        <RouterLink class="btn" to="/road">前往台账登记道路设施</RouterLink>
      </div>
    </div>

    <template v-else>
      <!-- 病害整表为空的空态说明 -->
      <div v-if="!loading && totals.diseaseTotal === 0" class="notice-banner">
        <span>还没有任何病害登记记录，各格的“最近病害数”暂时都是 0。可先去病害登记录入，再回来刷新。</span>
        <button class="link" type="button" @click="reload()">刷新</button>
      </div>

      <div v-for="group in groups" :key="`${group.level}-${group.unit}`" class="group-row">
        <div class="group-head">
          <span class="group-name">
            <em>{{ group.level }}</em>
            <i>/</i>
            {{ group.unit }}
          </span>
          <span class="group-meta">
            {{ group.roadCount }} 条设施 · 最近{{ recentDays }}天病害 {{ group.recentDiseaseCount }} · 未闭环计划
            {{ group.openPlanCount }}
          </span>
        </div>
        <div class="card-grid">
          <button
            v-for="road in group.roads"
            :key="String(road.id)"
            :ref="(el) => bindCardEl(el as Element | null, road.id)"
            type="button"
            class="road-card"
            :class="{ 'is-active': activeId === road.id }"
            @click="openDetail(road.id)"
          >
            <span class="road-card-name">{{ road.name }}</span>
            <span class="road-card-code">{{ road.code }} · {{ road.status }}</span>
            <span class="road-card-counts">
              <span class="count-pill" :class="{ zero: road.recentDiseaseCount === 0 }">
                最近病害 <strong>{{ road.recentDiseaseCount }}</strong>
              </span>
              <span class="count-pill" :class="{ zero: road.openPlanCount === 0, warn: road.openPlanCount > 0 }">
                未闭环计划 <strong>{{ road.openPlanCount }}</strong>
              </span>
            </span>
            <span v-if="road.recentDiseaseCount === 0" class="road-card-hint">最近{{ recentDays }}天未登记病害</span>
            <span v-else-if="road.latestDiseaseDate" class="road-card-hint">最近病害登记于 {{ road.latestDiseaseDate }}</span>
          </button>
        </div>
      </div>

      <footer class="reconcile-foot">
        <span v-if="ledgerTotal === null" class="muted">正在与台账核对条数…</span>
        <span v-else-if="ledgerTotal === totals.roads" class="ok-text">
          台账共 {{ ledgerTotal }} 条道路设施，与总览合计 {{ totals.roads }} 条一致
        </span>
        <span v-else class="error-text">
          台账 {{ ledgerTotal }} 条与总览合计 {{ totals.roads }} 条不一致，请点右上角刷新
        </span>
        <span class="muted">共 {{ groups.length }} 个分组，数据生成于 {{ generatedAt || '—' }}</span>
      </footer>
    </template>

    <!-- 单条详情抽屉 -->
    <div v-if="detail" class="drawer-mask" @click.self="closeDetail">
      <aside class="drawer" role="dialog" aria-modal="true" :aria-label="`${detail.road['道路名称']} 路况详情`">
        <header class="drawer-head">
          <div>
            <h3>{{ detail.road['道路名称'] }}（{{ detail.road['设施编码'] }}）</h3>
            <p class="muted">{{ detail.road['道路等级'] }} · {{ detail.road['管养单位'] }} · 当前状态 {{ detail.road.status }}</p>
          </div>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </header>

        <p v-if="drawerMessage" :class="drawerOk ? 'ok-text' : 'error-text'">{{ drawerMessage }}</p>

        <div class="drawer-actions">
          <button
            v-for="action in roadActions"
            :key="action"
            class="btn"
            type="button"
            :disabled="busy"
            @click="runRoadAction(action)"
          >
            {{ action }}
          </button>
        </div>

        <section class="drawer-block">
          <h4>调整分组信息</h4>
          <form class="edit-form" @submit.prevent="saveEdit">
            <label class="filter-item">
              <span>道路等级</span>
              <input v-model="editLevel" list="road-levels" placeholder="如：主干路" />
            </label>
            <label class="filter-item">
              <span>管养单位</span>
              <input v-model="editUnit" list="road-units" placeholder="如：市政一公司" />
            </label>
            <datalist id="road-levels">
              <option v-for="level in levelOptions" :key="level" :value="level" />
            </datalist>
            <datalist id="road-units">
              <option v-for="unit in unitOptions" :key="unit" :value="unit" />
            </datalist>
            <button class="btn primary" type="submit" :disabled="busy">保存并回到分组</button>
          </form>
        </section>

        <section class="drawer-block">
          <h4>
            关联病害
            <span class="muted">（共 {{ detail.diseaseCount }} 条，最近{{ detail.recentDays }}天 {{ detail.recentDiseaseCount }} 条）</span>
          </h4>
          <table class="data-table inner-table">
            <thead>
              <tr>
                <th>病害编号</th><th>病害类型</th><th>病害位置</th><th>严重等级</th><th>发现日期</th><th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in detail.diseases" :key="String(d.id)">
                <td>{{ d['病害编号'] ?? '—' }}</td>
                <td>{{ d['病害类型'] ?? '—' }}</td>
                <td>{{ d['病害位置'] ?? '—' }}</td>
                <td>{{ d['严重等级'] ?? '—' }}</td>
                <td>{{ d['发现日期'] ?? '—' }}</td>
                <td>{{ d['病害状态'] ?? d.status ?? '—' }}</td>
              </tr>
              <tr v-if="!detail.diseases.length">
                <td colspan="6" class="empty-state">
                  该道路暂未登记过病害。可在「病害登记」录入后
                  <button class="link" type="button" @click="refreshDetail">刷新本页</button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="drawer-block">
          <h4>
            养护计划与施工进度
            <span class="muted">
              （{{ detail.openPlanCount }} 个计划未闭环 · 关联施工 {{ detail.workProgress.total }} 项
              <template v-if="detail.workProgress.total">
                ：<span v-for="(count, status) in detail.workProgress.byStatus" :key="status">{{ status }} {{ count }} </span>
              </template>
              ）
            </span>
          </h4>
          <div v-if="!detail.plans.length" class="inner-empty">
            该道路暂无养护计划，因此也没有施工进度。
            <button class="link" type="button" @click="refreshDetail">刷新</button>
          </div>
          <article v-for="item in detail.plans" :key="String(item.plan.id)" class="plan-item">
            <header class="plan-head">
              <span>{{ item.plan['计划编号'] }} · {{ item.plan['养护类型'] }}</span>
              <span class="status-badge" :class="item.closed ? 'closed' : 'open'">
                {{ item.closed ? (item.closeReason || '已闭环') : '未闭环' }}
              </span>
            </header>
            <p class="muted">
              {{ item.plan['计划工期'] }} · 预算 {{ item.plan['预算金额'] }} 万元 · 计划状态
              {{ item.plan['计划状态'] ?? item.plan.status }}
            </p>
            <table v-if="item.works.length" class="data-table inner-table">
              <thead>
                <tr>
                  <th>施工编号</th><th>承接单位</th><th>开工日期</th><th>完工日期</th><th>完成工程量</th><th>施工状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in item.works" :key="String(w.id)">
                  <td>{{ w['施工编号'] }}</td>
                  <td>{{ w['承接单位'] }}</td>
                  <td>{{ w['开工日期'] || '—' }}</td>
                  <td>{{ w['完工日期'] || '—' }}</td>
                  <td>{{ w['完成工程量'] }}</td>
                  <td>{{ w['施工状态'] ?? w.status }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="muted plan-no-work">尚未下达施工任务</p>
          </article>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

interface RoadCard {
  id: number
  code: string
  name: string
  level: string
  unit: string
  status: string
  recentDiseaseCount: number
  openPlanCount: number
  latestDiseaseDate: string | null
}

interface RoadGroup {
  level: string
  unit: string
  roadCount: number
  recentDiseaseCount: number
  openPlanCount: number
  roads: RoadCard[]
}

interface OverviewSummary {
  generatedAt: string
  recentDays: number
  totals: { roads: number; groups: number; recentDiseases: number; openPlans: number; diseaseTotal: number }
  groups: RoadGroup[]
}

interface PlanDetail {
  plan: Row
  closed: boolean
  closeReason: string
  works: Row[]
}

interface RoadDetail {
  road: Row
  recentDays: number
  diseaseCount: number
  recentDiseaseCount: number
  diseases: Row[]
  plans: PlanDetail[]
  openPlanCount: number
  workProgress: { total: number; byStatus: Record<string, number> }
}

const LAST_ROAD_KEY = 'road-overview:lastRoadId'
const roadActions = ['办理移交', '标记观测', '封闭设施']

const loading = ref(false)
const busy = ref(false)
const errorMessage = ref('')
const drawerMessage = ref('')
const drawerOk = ref(true)

const recentDays = ref(30)
const generatedAt = ref('')
const groups = ref<RoadGroup[]>([])
const totals = ref<OverviewSummary['totals']>({
  roads: 0,
  groups: 0,
  recentDiseases: 0,
  openPlans: 0,
  diseaseTotal: 0,
})
const ledgerTotal = ref<number | null>(null)

const detail = ref<RoadDetail | null>(null)
const activeId = ref<number | null>(null)
const editLevel = ref('')
const editUnit = ref('')
const cardEls = new Map<number, Element>()

const inViewStats = computed(() => [
  { label: '道路设施合计', value: totals.value.roads },
  { label: '分组数量', value: totals.value.groups },
  { label: `最近${recentDays.value}天登记病害`, value: totals.value.recentDiseases },
  { label: '未闭环养护计划', value: totals.value.openPlans },
])

const levelOptions = computed(() => Array.from(new Set(groups.value.map((g) => g.level))))
const unitOptions = computed(() => Array.from(new Set(groups.value.map((g) => g.unit))))

function bindCardEl(el: Element | null, id: number) {
  if (el) {
    cardEls.set(id, el)
  } else {
    cardEls.delete(id)
  }
}

async function fetchSummary() {
  const response = await request('/api/road/overview/summary')
  if (!response.ok) {
    throw new Error('路况总览读取失败')
  }
  return (await response.json()) as OverviewSummary
}

async function fetchLedgerTotal() {
  const response = await request('/api/road?size=1')
  if (!response.ok) {
    return null
  }
  const payload = (await response.json()) as { total?: number }
  return typeof payload.total === 'number' ? payload.total : null
}

async function reload(options: { focusId?: number | null; scroll?: boolean } = {}) {
  loading.value = true
  errorMessage.value = ''
  try {
    const [summary, ledger] = await Promise.all([fetchSummary(), fetchLedgerTotal()])
    recentDays.value = summary.recentDays
    generatedAt.value = summary.generatedAt
    groups.value = summary.groups
    totals.value = summary.totals
    ledgerTotal.value = ledger

    const scroll = Boolean(options.scroll)
    const wantedId = options.focusId === undefined ? rememberLastId() : options.focusId
    if (wantedId !== null && summary.groups.some((g) => g.roads.some((r) => r.id === wantedId))) {
      await openDetail(wantedId, { scroll })
    } else if (wantedId !== null) {
      // 上次看的道路已不在台账，清掉记忆避免反复落空
      localStorage.removeItem(LAST_ROAD_KEY)
      detail.value = null
      activeId.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路况总览加载失败'
  } finally {
    loading.value = false
  }
}

function rememberLastId(): number | null {
  const raw = localStorage.getItem(LAST_ROAD_KEY)
  const id = raw === null ? NaN : Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
}

async function openDetail(id: number, options: { scroll?: boolean } = {}) {
  activeId.value = id
  localStorage.setItem(LAST_ROAD_KEY, String(id))
  drawerMessage.value = ''
  try {
    const response = await request(`/api/road/overview/${id}`)
    if (!response.ok) {
      throw new Error('道路详情读取失败')
    }
    detail.value = (await response.json()) as RoadDetail
    editLevel.value = String(detail.value.road['道路等级'] ?? '')
    editUnit.value = String(detail.value.road['管养单位'] ?? '')
  } catch (error) {
    drawerMessage.value = error instanceof Error ? error.message : '道路详情加载失败'
    drawerOk.value = false
  }
  if (options.scroll) {
    await nextTick()
    cardEls.get(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

async function refreshDetail() {
  if (activeId.value !== null) {
    await openDetail(activeId.value)
  }
}

function closeDetail() {
  // 记忆保留：再次进入视图时仍停在刚才看的那一条
  detail.value = null
}

async function saveEdit() {
  if (activeId.value === null) {
    return
  }
  drawerMessage.value = ''
  const level = editLevel.value.trim()
  const unit = editUnit.value.trim()
  if (!level || !unit) {
    drawerOk.value = false
    drawerMessage.value = '道路等级与管养单位都不允许清空'
    return
  }
  busy.value = true
  try {
    const response = await request(`/api/road/${activeId.value}`, {
      method: 'PATCH',
      body: JSON.stringify({ values: { 道路等级: level, 管养单位: unit } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    drawerOk.value = Boolean(payload.ok)
    drawerMessage.value = payload.message
    if (!payload.ok) {
      return
    }
    // 分组可能已经变化：重拉总览，再把详情刷新到新数据上
    await reload({ focusId: activeId.value })
    drawerOk.value = true
    drawerMessage.value = payload.message
  } catch (error) {
    drawerOk.value = false
    drawerMessage.value = error instanceof Error ? error.message : '保存失败，请稍后重试'
  } finally {
    busy.value = false
  }
}

async function runRoadAction(action: string) {
  if (activeId.value === null) {
    return
  }
  busy.value = true
  drawerMessage.value = ''
  try {
    const response = await request(`/api/road/${activeId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    drawerOk.value = Boolean(payload.ok)
    drawerMessage.value = payload.message
    if (payload.ok) {
      await reload({ focusId: activeId.value })
      drawerOk.value = true
      drawerMessage.value = payload.message
    }
  } catch (error) {
    drawerOk.value = false
    drawerMessage.value = error instanceof Error ? error.message : '动作执行失败，请稍后重试'
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void reload({ scroll: true })
})
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; align-items: center; }
.page-actions .btn { text-decoration: none; color: #1f2937; display: inline-flex; align-items: center; }
.error-banner {
  display: flex; gap: 8px; align-items: center;
  background: #fef3f2; border: 1px solid #fda29b; color: #b42318;
  border-radius: 6px; padding: 8px 12px; font-size: 13px;
}
.notice-banner {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  background: #fffaeb; border: 1px solid #fedf89; color: #b54708;
  border-radius: 6px; padding: 8px 12px; font-size: 13px; margin-bottom: 12px;
}
.group-row { margin-bottom: 14px; }
.group-head {
  display: flex; justify-content: space-between; align-items: baseline;
  background: #eef2f7; border: 1px solid var(--border); border-bottom: none;
  border-radius: 8px 8px 0 0; padding: 8px 12px;
}
.group-name { font-weight: 600; font-size: 14px; }
.group-name em { font-style: normal; color: var(--brand); }
.group-name i { color: var(--muted); font-style: normal; margin: 0 6px; }
.group-meta { font-size: 12px; color: var(--muted); }
.card-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 10px; border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 8px 8px; padding: 10px 12px; background: #fff;
}
.road-card {
  text-align: left; border: 1px solid var(--border); border-radius: 8px;
  background: #fff; padding: 10px 12px; cursor: pointer; display: flex;
  flex-direction: column; gap: 6px; transition: border-color .15s, box-shadow .15s;
}
.road-card:hover { border-color: var(--brand); box-shadow: 0 2px 8px rgba(31, 111, 235, .12); }
.road-card.is-active { border-color: var(--brand); box-shadow: 0 0 0 2px rgba(31, 111, 235, .25); }
.road-card-name { font-weight: 600; font-size: 14px; }
.road-card-code { font-size: 12px; color: var(--muted); }
.road-card-counts { display: flex; gap: 6px; flex-wrap: wrap; }
.count-pill {
  font-size: 12px; border-radius: 999px; padding: 2px 8px;
  background: #eef4ff; color: #1d4ed8;
}
.count-pill strong { margin-left: 2px; }
.count-pill.zero { background: #f1f5f9; color: var(--muted); }
.count-pill.warn { background: #fef3f2; color: #b42318; }
.road-card-hint { font-size: 11px; color: var(--muted); }
.overview-empty {
  background: #fff; border: 1px dashed var(--border); border-radius: 8px;
  padding: 40px 20px; text-align: center;
}
.empty-title { font-size: 16px; font-weight: 600; margin: 0 0 8px; }
.empty-desc { color: var(--muted); font-size: 13px; margin: 0 0 16px; }
.empty-actions { display: flex; gap: 10px; justify-content: center; }
.empty-actions .btn { text-decoration: none; color: #1f2937; }
.reconcile-foot {
  display: flex; justify-content: space-between; gap: 12px;
  margin-top: 10px; font-size: 12px;
}
.muted { color: var(--muted); font-size: 12px; }
.ok-text { color: #067647; font-size: 13px; }
.drawer-mask {
  position: fixed; inset: 0; background: rgba(16, 24, 40, .45);
  display: flex; justify-content: flex-end; z-index: 50;
}
.drawer {
  width: min(760px, 92vw); height: 100%; background: #fff; overflow-y: auto;
  padding: 16px 20px; box-shadow: -8px 0 24px rgba(16, 24, 40, .2);
}
.drawer-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 12px;
}
.drawer-head h3 { margin: 0 0 4px; font-size: 16px; }
.drawer-actions { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.drawer-block { margin-bottom: 18px; }
.drawer-block h4 { margin: 0 0 8px; font-size: 14px; }
.edit-form { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.edit-form .filter-item { flex: 1; min-width: 180px; }
.edit-form .btn { height: 30px; }
.inner-table { font-size: 12px; }
.inner-empty {
  font-size: 13px; color: var(--muted); background: #f8fafc;
  border: 1px dashed var(--border); border-radius: 6px; padding: 10px 12px;
}
.plan-item { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.plan-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 13px; }
.status-badge { font-size: 12px; border-radius: 999px; padding: 2px 10px; font-weight: 400; }
.status-badge.open { background: #fef3f2; color: #b42318; }
.status-badge.closed { background: #ecfdf3; color: #067647; }
.plan-no-work { margin: 6px 0 0; }
</style>
