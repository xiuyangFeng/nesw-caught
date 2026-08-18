"""条件组合器 DSL。操作数只能引用因子注册表。"""

from __future__ import annotations

from typing import Any

from app.services.quant.factors import FACTOR_REGISTRY

OPS = {">", "<", ">=", "<="}


def validate_dsl(dsl: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if dsl.get("sleeve") not in {"event_catalyst", "trend_flow", "fundamental_revalue"}:
        errors.append("sleeve_required")
    if not dsl.get("horizon"):
        errors.append("horizon_required")
    _walk(dsl, errors, depth=0)
    return errors


def _walk(node: dict[str, Any], errors: list[str], *, depth: int) -> None:
    if depth > 3:
        errors.append("nesting_gt_3")
        return
    if "factor" in node:
        if node["factor"] not in FACTOR_REGISTRY:
            errors.append(f"unknown_factor:{node['factor']}")
        if node.get("op") not in OPS:
            errors.append("bad_op")
        return
    for child in node.get("conditions") or []:
        _walk(child, errors, depth=depth + 1)


def evaluate_dsl(dsl: dict[str, Any], features: dict[str, float]) -> bool:
    if validate_dsl(dsl):
        return False
    return _eval_node(dsl, features)


def _eval_node(node: dict[str, Any], features: dict[str, float]) -> bool:
    if "factor" in node:
        left = features.get(node["factor"])
        if left is None:
            return False
        op = node["op"]
        right = float(node["value"])
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        return left <= right
    children = node.get("conditions") or []
    if not children:
        return False
    results = [_eval_node(child, features) for child in children]
    if node.get("logic") == "or":
        return any(results)
    return all(results)
