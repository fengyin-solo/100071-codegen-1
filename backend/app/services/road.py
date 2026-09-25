"""道路设施业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "road"
REQUIRED_FIELDS = ["设施编码", "道路名称", "道路等级"]
EDITABLE_FIELDS = ["道路等级", "管养单位"]
STATUS_ORDER = ["待移交", "正常养护", "重点观测", "封闭施工"]
ACTION_RULES = {"办理移交": "正常养护", "标记观测": "重点观测", "封闭设施": "封闭施工"}
NEGATIVE_ACTIONS = []


class RoadService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设施编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """在路况总览里就地修改道路等级、管养单位等字段；台账读到的是同一条记录。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"道路设施 {entry_id} 不存在或已归档"
        changed: dict[str, str] = {}
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            value = str(values.get(field) or "").strip()
            if not value:
                return None, f"字段「{field}」不允许清空"
            if entry.get(field) != value:
                entry[field] = value
                changed[field] = value
        if not changed:
            return entry, "道路设施信息未发生变化"
        return entry, "道路设施已更新：" + "、".join(changed)

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
        return entry, f"道路设施已{action}"
