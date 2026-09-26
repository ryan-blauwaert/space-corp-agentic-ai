"""Render trusted evidence with fixed domain wording; never accept generated prose."""

import hashlib
import html
import json
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from app.answers.contracts import (
    Answered,
    AnswerOutcome,
    AnswerRequest,
    EvidenceFact,
    FacilityFact,
    FactSelection,
    IncidentFact,
    InventoryFact,
    RecordReference,
    RenderedAnswer,
    StockFact,
    WorkOrderFact,
)
from app.answers.validation import (
    cautious_response,
    evidence_references,
    failed_answer,
    validate_selection,
)
from app.queries.contracts import IncidentsPlan, WorkOrdersPlan


def evidence_facts(request: AnswerRequest) -> tuple[EvidenceFact, ...]:
    """Snapshot-bound facts. Input requests remain trusted internal application data."""
    request = AnswerRequest.model_validate(request.model_dump(warnings=False))
    if cautious_response(request) is not None:
        return ()
    assert request.query.response is not None
    # Bind presentation IDs to context, resolved scope, evidence, and original question.
    snapshot = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    result = request.query.response.result
    if result.operation == "facility_equipment":
        return tuple(
            FacilityFact(fact_id=f"{snapshot}:{i}", evidence=row)
            for i, row in enumerate(result.page.rows)
        )
    if result.operation == "compatible_stock":
        return tuple(
            StockFact(fact_id=f"{snapshot}:{i}", evidence=row)
            for i, row in enumerate(result.page.rows)
        )
    if result.operation == "work_orders":
        return tuple(
            WorkOrderFact(fact_id=f"{snapshot}:{i}", evidence=row)
            for i, row in enumerate(result.page.rows)
        )
    if result.operation == "incidents":
        return tuple(
            IncidentFact(fact_id=f"{snapshot}:{i}", evidence=row)
            for i, row in enumerate(result.page.rows)
        )
    return tuple(
        InventoryFact(fact_id=f"{snapshot}:{i}", evidence=row)
        for i, row in enumerate(result.page.rows)
    )


def _quoted(value: str) -> str:
    """Keep stored text a quoted literal, including in Markdown-capable clients.

    JSON escapes controls; HTML entities neutralize markup and backslashes. The output
    contract is plain text and downstream UI must also use text-safe rendering.
    """
    quoted = html.escape(json.dumps(value, ensure_ascii=True), quote=True)
    for char in "\\`*_[]()#!|~":
        quoted = quoted.replace(char, f"&#{ord(char)};")
    return quoted


def _time(value: datetime | None) -> str:
    return value.isoformat().replace("+00:00", "Z") if value else "not recorded"


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _record(
    kind: str, identity: UUID | None, code: str | None = None, name: str | None = None
) -> str:
    if identity is None:
        return "not recorded"
    # Stored labels are quoted plain-text literals, never instructions or markup.
    # Codes disambiguate names; older saved evidence falls back to its exact UUID.
    if code:
        label = (
            json.dumps(name, ensure_ascii=True) + " (" + json.dumps(code) + ")"
            if name
            else json.dumps(code)
        )
        return f"{kind} {label}"
    return f"{kind} {identity}"


def _sentence(fact: EvidenceFact) -> str:
    if isinstance(fact, FacilityFact):
        facility = fact.evidence
        unit_labels = {u.unit_id: u.asset_tag for u in facility.units}
        units = "; ".join(
            f"{_record('unit', u.unit_id, u.asset_tag)} is {u.operational_status}"
            for u in facility.units
        )
        incidents = "; ".join(
            f"{_record('incident', i.incident_id, i.reference_code)} is {i.status} on "
            f"{_record('unit', i.equipment_unit_id, unit_labels.get(i.equipment_unit_id))}"
            for i in facility.incidents
        )
        return (
            f"{_record('Facility', facility.facility_id, facility.facility_code, facility.facility_name)}: {units}. "
            + (
                f"Supporting incidents: {incidents}."
                if incidents
                else "No supporting incidents were returned for these units."
            )
        )
    if isinstance(fact, StockFact):
        stock = fact.evidence
        quantity = (
            "no inventory record was returned; stock quantity is unknown"
            if stock.inventory_id is None
            else (
                f"recorded stock quantity {stock.quantity_on_hand}"
                if stock.component_code
                else f"inventory {stock.inventory_id} records quantity {stock.quantity_on_hand}"
            )
        )
        return (
            f"{_record('Component', stock.component_id, stock.component_code, stock.component_name)} "
            f"is compatible with {_record('model', stock.model_id, stock.model_code, stock.model_name)}; {quantity}."
        )
    if isinstance(fact, WorkOrderFact):
        order = fact.evidence
        return (
            f"{_record('Work order', order.work_order_id, order.reference_code)} at "
            f"{_record('facility', order.facility_id, order.facility_code, order.facility_name)}: "
            f"status {order.status.replace('_', ' ')}, priority {order.priority}, "
            f"due date {_time(order.due_at)}, overdue {_yes(order.overdue)}, blocked {_yes(order.blocked)}. "
            f"Originating incident: {_record('incident', order.originating_incident_id, order.originating_incident_code)}; "
            f"incident-affected unit: {_record('unit', order.incident_equipment_unit_id, order.incident_equipment_asset_tag)}; "
            f"direct target: {_record('unit', order.target_equipment_unit_id, order.target_equipment_asset_tag)}."
        )
    if isinstance(fact, IncidentFact):
        incident = fact.evidence
        fault = _quoted(incident.fault_code) if incident.fault_code is not None else "not recorded"
        return (
            f"{_record('Incident', incident.incident_id, incident.reference_code)} at "
            f"{_record('facility', incident.facility_id, incident.facility_code, incident.facility_name)}: "
            f"affected unit: {_record('unit', incident.unit_id, incident.asset_tag)}, status {incident.status}, "
            f"severity {incident.severity}, fault code {fault}, occurred at {_time(incident.occurred_at)}."
        )
    inventory = fact.evidence
    if inventory.facility_code and inventory.component_code:
        return (
            f"{_record('Facility', inventory.facility_id, inventory.facility_code, inventory.facility_name)} "
            f"has {inventory.quantity_on_hand} in stock of "
            f"{_record('component', inventory.component_id, inventory.component_code, inventory.component_name)}: "
            f"reorder point {inventory.reorder_point}, shortfall {inventory.shortfall}."
        )
    return (
        f"Inventory {inventory.inventory_id} at facility {inventory.facility_id} for component "
        f"{inventory.component_id}: quantity {inventory.quantity_on_hand}, reorder point "
        f"{inventory.reorder_point}, shortfall {inventory.shortfall}."
    )


def _summary(request: AnswerRequest) -> list[str]:
    assert request.query.response is not None
    result = request.query.response.result
    page = result.page
    nouns = {
        "facility_equipment": ("facility", "facilities"),
        "compatible_stock": ("compatible component", "compatible components"),
        "work_orders": ("work order", "work orders"),
        "incidents": ("incident", "incidents"),
        "inventory": ("inventory record", "inventory records"),
    }
    noun = nouns[result.operation][0 if page.total == 1 else 1]
    verb = "was" if page.total == 1 else "were"
    lines = [
        f"Within the executed query scope and filters, {page.total} matching {noun} {verb} found."
    ]
    if page.offset != 0 or len(page.rows) != page.total:
        lines.append(
            f"Partial results: this page contains {len(page.rows)} of {page.total} matches (offset {page.offset})."
        )
    else:
        lines.append("All matching records are included below.")
    plan = request.query.plan
    if isinstance(plan, WorkOrdersPlan):
        lines.append(f"Overdue flags are as of {_time(plan.as_of)}.")
    if result.operation in ("facility_equipment", "compatible_stock"):
        if getattr(plan, "incident_statuses", None) is None:
            lines.append("Incident evidence was not required by this query.")
    if result.operation == "compatible_stock" and result.incident_ids:
        lines.append(
            "Supporting incidents: "
            + ", ".join(json.dumps(code) for code in result.incident_codes)
            + "."
            if result.incident_codes
            else "Supporting incidents: " + ", ".join(str(i) for i in result.incident_ids) + "."
        )
    if result.operation == "compatible_stock" and not result.incident_ids:
        lines.append("No supporting incidents were returned for this query.")
    # A count alone does not imply recurrence: require the same fault in a declared
    # interval, under the executed filters, with the complete result available.
    if isinstance(plan, IncidentsPlan) and result.operation == "incidents":
        if plan.fault_code and plan.occurred:
            rows = result.page.rows
            consistent = all(
                (plan.equipment_unit_id is None or r.unit_id == plan.equipment_unit_id)
                and r.fault_code == plan.fault_code
                and plan.occurred.start <= r.occurred_at < plan.occurred.end
                for r in rows
            )
            if consistent and page.offset == 0 and len(rows) == page.total:
                interval = f"[{_time(plan.occurred.start)}, {_time(plan.occurred.end)})"
                if result.count >= 2:
                    lines.append(
                        f"The returned incidents establish recurrence of the same fault within {interval}, under the executed filters."
                    )
                else:
                    lines.append(f"One incident does not establish recurrence within {interval}.")
    return lines


def render_answer(request: AnswerRequest, selection: FactSelection | None = None) -> AnswerOutcome:
    """Only input preferences are bounded fact IDs. Always rebuild facts from evidence.

    Invalid trusted input raises. Invalid preferences and oversized output are withheld;
    no truncation, model fallback, extra query, or scope approval occurs here.
    """
    request = AnswerRequest.model_validate(request.model_dump(warnings=False))
    cautious = cautious_response(request)
    if cautious is not None:
        return cautious
    assert request.query.response is not None
    facts = evidence_facts(request)
    by_id = {fact.fact_id: fact for fact in facts}
    if selection is not None:
        if not validate_selection(selection, set(by_id)):
            return failed_answer("invalid_answer")
        selected = selection.fact_ids
    else:
        selected = ()
    order = (*selected, *(f.fact_id for f in facts if f.fact_id not in selected))
    lines = _summary(request) + [_sentence(by_id[key]) for key in order]
    result = request.query.response.result
    # References come only from included evidence, including supporting relationships.
    references: tuple[RecordReference, ...] = tuple(
        sorted(evidence_references(result), key=lambda r: (r.entity, str(r.record_id)))
    )
    try:
        answer = RenderedAnswer(text="\n".join(lines), references=references)
    except ValidationError:
        return failed_answer("invalid_answer")
    page = result.page
    return Answered(
        answer=answer,
        coverage="complete" if page.offset == 0 and len(page.rows) == page.total else "partial",
    )
