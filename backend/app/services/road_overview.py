"""路况总览业务规则：把道路设施按道路等级、管养单位聚合成排，并补齐病害与养护进度。

总览与台账共用同一个内存仓库（app.store），因此在总览里改了道路等级或管养单位，
台账重新拉取时拿到的就是同一条记录，合计天然对得上。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

ROAD_MODULE = "road"
DISEASE_MODULE = "disease"
PLAN_MODULE = "plan"
WORK_MODULE = "work"

# 分组时道路等级的固定先后，未登记的等级排在后面
ROAD_LEVEL_ORDER = ["快速路", "主干路", "次干路", "支路"]
# “最近登记病害”的统计窗口
RECENT_DAYS = 30
# 走到这些状态的养护计划视为已闭环：作废也算终止；施工已完工代表计划落地闭环
PLAN_CLOSED_STATUSES = {"已作废"}
WORK_DONE_STATUS = "已完工"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_day(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


class RoadOverviewService:
    def __init__(self) -> None:
        self.today = date.today()
        self.recent_after = self.today - timedelta(days=RECENT_DAYS)

    # -- 关联关系 ---------------------------------------------------------

    def _diseases_of(self, road_name: str) -> list[dict[str, Any]]:
        return [
            row for row in store.rows(DISEASE_MODULE)
            if _text(row.get("所在设施")) == road_name
        ]

    def _plans_of(self, road_name: str) -> list[dict[str, Any]]:
        return [
            row for row in store.rows(PLAN_MODULE)
            if _text(row.get("养护对象")) == road_name
        ]

    def _works_of_plan(self, plan_code: str) -> list[dict[str, Any]]:
        return [
            row for row in store.rows(WORK_MODULE)
            if _text(row.get("关联计划")) == plan_code
        ]

    def _plan_closed(self, plan: dict[str, Any], works: list[dict[str, Any]]) -> tuple[bool, str]:
        if _text(plan.get("status")) in PLAN_CLOSED_STATUSES or _text(plan.get("计划状态")) in PLAN_CLOSED_STATUSES:
            return True, "计划已作废"
        if any(_text(work.get("status")) == WORK_DONE_STATUS or _text(work.get("施工状态")) == WORK_DONE_STATUS for work in works):
            return True, "关联施工已完工"
        return False, ""

    def _recent_diseases(self, diseases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            row for row in diseases
            if (day := _parse_day(row.get("发现日期"))) is not None and day >= self.recent_after
        ]

    # -- 聚合视图 ---------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        roads = store.rows(ROAD_MODULE)
        groups_map: dict[tuple[str, str], list[dict[str, Any]]] = {}

        recent_total = 0
        open_plan_total = 0

        for road in roads:
            level = _text(road.get("道路等级")) or "未分级"
            unit = _text(road.get("管养单位")) or "未指派单位"
            name = _text(road.get("道路名称"))

            diseases = self._diseases_of(name)
            recent = self._recent_diseases(diseases)
            open_plans = 0
            for plan in self._plans_of(name):
                closed, _ = self._plan_closed(plan, self._works_of_plan(_text(plan.get("计划编号"))))
                if not closed:
                    open_plans += 1

            latest = max((_parse_day(row.get("发现日期")) for row in recent), default=None)

            card = {
                "id": road.get("id"),
                "code": _text(road.get("设施编码")),
                "name": name,
                "level": level,
                "unit": unit,
                "status": _text(road.get("status")) or _text(road.get("设施状态")),
                "recentDiseaseCount": len(recent),
                "openPlanCount": open_plans,
                "latestDiseaseDate": latest.isoformat() if latest else None,
            }
            recent_total += len(recent)
            open_plan_total += open_plans
            groups_map.setdefault((level, unit), []).append(card)

        def level_rank(level: str) -> int:
            return ROAD_LEVEL_ORDER.index(level) if level in ROAD_LEVEL_ORDER else len(ROAD_LEVEL_ORDER)

        groups: list[dict[str, Any]] = []
        for (level, unit) in sorted(groups_map, key=lambda key: (level_rank(key[0]), key[1])):
            cards = sorted(groups_map[(level, unit)], key=lambda card: int(card.get("id") or 0))
            groups.append({
                "level": level,
                "unit": unit,
                "roadCount": len(cards),
                "recentDiseaseCount": sum(int(card["recentDiseaseCount"]) for card in cards),
                "openPlanCount": sum(int(card["openPlanCount"]) for card in cards),
                "roads": cards,
            })

        return {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "recentDays": RECENT_DAYS,
            "totals": {
                "roads": len(roads),
                "groups": len(groups),
                "recentDiseases": recent_total,
                "openPlans": open_plan_total,
                "diseaseTotal": len(store.rows(DISEASE_MODULE)),
            },
            "groups": groups,
        }

    # -- 单条详情 ---------------------------------------------------------

    def detail(self, entry_id: int) -> dict[str, Any] | None:
        road = store.find(ROAD_MODULE, entry_id)
        if road is None:
            return None

        name = _text(road.get("道路名称"))
        diseases = sorted(
            self._diseases_of(name),
            key=lambda row: (_parse_day(row.get("发现日期")) or date.min),
            reverse=True,
        )

        plans: list[dict[str, Any]] = []
        work_status_counter: dict[str, int] = {}
        for plan in self._plans_of(name):
            works = sorted(self._works_of_plan(_text(plan.get("计划编号"))), key=lambda row: int(row.get("id") or 0))
            closed, close_reason = self._plan_closed(plan, works)
            for work in works:
                status = _text(work.get("status")) or _text(work.get("施工状态")) or "未知状态"
                work_status_counter[status] = work_status_counter.get(status, 0) + 1
            plans.append({
                "plan": plan,
                "closed": closed,
                "closeReason": close_reason,
                "works": works,
            })
        plans.sort(key=lambda item: int(item["plan"].get("id") or 0))

        recent = self._recent_diseases(diseases)
        return {
            "road": road,
            "recentDays": RECENT_DAYS,
            "diseaseCount": len(diseases),
            "recentDiseaseCount": len(recent),
            "diseases": diseases,
            "plans": plans,
            "openPlanCount": sum(1 for item in plans if not item["closed"]),
            "workProgress": {
                "total": sum(work_status_counter.values()),
                "byStatus": work_status_counter,
            },
        }
