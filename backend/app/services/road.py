"""道路设施业务规则：状态流转、字段校验、路况总览与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "road"
REQUIRED_FIELDS = ["设施编码", "道路名称", "道路等级"]
OPTIONAL_FIELDS = ["起止桩号", "路面结构", "管养单位", "建成年份"]
EDITABLE_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_ORDER = ["待移交", "正常养护", "重点观测", "封闭施工"]
ACTION_RULES = {"办理移交": "正常养护", "标记观测": "重点观测", "封闭设施": "封闭施工"}
NEGATIVE_ACTIONS = []
CLOSED_PLAN_STATUSES = {"已作废", "已闭环"}


class RoadService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        level: str | None = None,
        unit: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("设施编码", "")) or keyword in str(row.get("道路名称", ""))
            ]
        if name:
            rows = [row for row in rows if name in str(row.get("道路名称", ""))]
        if level:
            rows = [row for row in rows if level in str(row.get("道路等级", ""))]
        if unit:
            rows = [row for row in rows if unit in str(row.get("管养单位", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str] | str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        code = str(values.get("设施编码") or "").strip()
        if any(str(row.get("设施编码") or "") == code for row in rows):
            return None, "设施编码已存在，请更换后再登记"
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field) or "").strip() for field in EDITABLE_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["设施状态"] = STATUS_ORDER[0]
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"道路设施 {entry_id} 不存在或已归档"
        updates = {field: str(values.get(field) or "").strip() for field in EDITABLE_FIELDS if field in values}
        missing = [field for field in REQUIRED_FIELDS if field in updates and not updates[field]]
        if missing:
            return None, f"必填字段不能为空：{'、'.join(missing)}"
        code = updates.get("设施编码", str(entry.get("设施编码") or ""))
        duplicated = any(
            int(row.get("id", 0)) != entry_id and str(row.get("设施编码") or "") == code
            for row in store.rows(MODULE)
        )
        if duplicated:
            return None, "设施编码已存在，请更换后再保存"
        entry.update(updates)
        return entry, "道路设施已保存"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"道路设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于道路设施可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["设施状态"] = target
        return entry, f"道路设施已{action}"

    def road_overview(self) -> dict[str, Any]:
        roads = store.rows(MODULE)
        diseases = store.rows("disease")
        plans = store.rows("plan")
        works = store.rows("work")
        disease_count = len(diseases)

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for road in roads:
            aliases = self._road_aliases(road)
            related_diseases = self._related_rows(diseases, aliases, "所在设施")
            related_plans = [
                plan for plan in plans
                if self._matches_road(plan.get("养护对象"), aliases)
                and str(plan.get("status") or plan.get("计划状态") or "") not in CLOSED_PLAN_STATUSES
            ]
            latest_disease = self._latest_disease(related_diseases)
            item = self._road_summary(road, related_diseases, related_plans, latest_disease)
            key = (str(road.get("道路等级") or "未分级"), str(road.get("管养单位") or "未分配单位"))
            grouped.setdefault(key, []).append(item)

        groups: list[dict[str, Any]] = []
        for (level, unit), items in grouped.items():
            items.sort(key=lambda item: (-int(item["disease_count"]), str(item["road_name"])))
            groups.append({
                "road_level": level,
                "maintenance_unit": unit,
                "count": len(items),
                "disease_count": sum(int(item["disease_count"]) for item in items),
                "open_plan_count": sum(int(item["open_plan_count"]) for item in items),
                "latest_disease_date": max(
                    (str(item["latest_disease_date"] or "") for item in items),
                    default="",
                ) or None,
                "items": items,
            })
        groups.sort(key=lambda group: (str(group["road_level"]), str(group["maintenance_unit"])))
        return {
            "total": len(roads),
            "disease_total": disease_count,
            "disease_count": disease_count,
            "open_plan_count": sum(int(group["open_plan_count"]) for group in groups),
            "groups": groups,
        }

    def road_detail(self, entry_id: int) -> dict[str, Any] | None:
        road = store.find(MODULE, entry_id)
        if road is None:
            return None
        aliases = self._road_aliases(road)
        diseases = self._related_rows(store.rows("disease"), aliases, "所在设施")
        plans = [plan for plan in store.rows("plan") if self._matches_road(plan.get("养护对象"), aliases)]
        plan_numbers = {str(plan.get("计划编号") or "") for plan in plans}
        works = [work for work in store.rows("work") if str(work.get("关联计划") or "") in plan_numbers]
        work_by_plan = self._group_works(works)

        plan_items = []
        for plan in sorted(plans, key=lambda row: str(row.get("计划编号") or "")):
            plan_id = str(plan.get("计划编号") or "")
            related_works = work_by_plan.get(plan_id, [])
            plan_items.append({
                "plan": plan,
                "works": related_works,
                "work_count": len(related_works),
                "progress": self._plan_progress(related_works),
            })

        return {
            "road": road,
            "diseases": sorted(diseases, key=lambda row: self._date_key(row.get("发现日期")), reverse=True),
            "plans": plan_items,
            "disease_count": len(diseases),
            "open_plan_count": sum(
                1 for plan in plans
                if str(plan.get("status") or plan.get("计划状态") or "") not in CLOSED_PLAN_STATUSES
            ),
        }

    def _road_summary(
        self,
        road: dict[str, Any],
        diseases: list[dict[str, Any]],
        open_plans: list[dict[str, Any]],
        latest_disease: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "id": road.get("id"),
            "road_code": road.get("设施编码"),
            "road_name": road.get("道路名称"),
            "road_level": road.get("道路等级") or "未分级",
            "maintenance_unit": road.get("管养单位") or "未分配单位",
            "status": road.get("status") or road.get("设施状态") or "待移交",
            "disease_count": len(diseases),
            "open_plan_count": len(open_plans),
            "latest_disease_date": latest_disease.get("发现日期") if latest_disease else None,
            "latest_disease_type": latest_disease.get("病害类型") if latest_disease else None,
        }

    def _road_aliases(self, road: dict[str, Any]) -> list[str]:
        aliases: list[str] = []
        for key in ("设施编码", "道路名称", "起止桩号"):
            value = str(road.get(key) or "").strip()
            if value and value not in aliases:
                aliases.append(value)
        return aliases

    def _related_rows(self, rows: list[dict[str, Any]], aliases: list[str], field: str) -> list[dict[str, Any]]:
        return [row for row in rows if self._matches_road(row.get(field), aliases)]

    def _matches_road(self, value: Any, aliases: list[str]) -> bool:
        text = str(value or "").strip()
        return bool(text) and any(alias == text or alias in text or text in alias for alias in aliases)

    def _latest_disease(self, diseases: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not diseases:
            return None
        return max(diseases, key=lambda row: (self._date_key(row.get("发现日期")), int(row.get("id", 0))))

    def _date_key(self, value: Any) -> str:
        return str(value or "")

    def _group_works(self, works: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for work in works:
            grouped.setdefault(str(work.get("关联计划") or ""), []).append(work)
        for items in grouped.values():
            items.sort(key=lambda row: str(row.get("施工编号") or ""))
        return grouped

    def _plan_progress(self, works: list[dict[str, Any]]) -> dict[str, Any]:
        if not works:
            return {"percent": 0, "status": "未开工", "completed_count": 0}
        total = len(works)
        completed = sum(1 for work in works if work.get("status") == "已完工")
        in_progress = sum(1 for work in works if work.get("status") == "施工中")
        waiting_acceptance = sum(1 for work in works if work.get("status") == "待验收")
        if completed == total:
            status = "已完工"
        elif waiting_acceptance:
            status = "待验收"
        elif in_progress:
            status = "施工中"
        else:
            status = "待开工"
        return {
            "percent": self._average_progress(works),
            "status": status,
            "completed_count": completed,
        }

    def _average_progress(self, works: list[dict[str, Any]]) -> int:
        percents = [self._work_progress(work) for work in works]
        return round(sum(percents) / len(percents)) if percents else 0

    def _work_progress(self, work: dict[str, Any]) -> int:
        text = str(work.get("完成工程量") or "").strip().rstrip("%")
        if text.replace(".", "", 1).isdigit():
            return max(0, min(100, round(float(text))))
        return {"待开工": 0, "施工中": 50, "待验收": 90, "已完工": 100}.get(str(work.get("status") or ""), 0)
