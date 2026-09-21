"""Publish and copy a frozen baseline; no HTTP or AI functionality."""

from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import Table, delete, func, select, text
from sqlalchemy.orm import Session

from app.baselines.models import BaselineRecord
from app.equipment.models import (
    CatalogReleaseRecord,
    ComponentRecord,
    EquipmentModelRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    equipment_model_components,
)
from app.facilities.models import FacilityRecord
from app.operations.models import IncidentRecord, WorkOrderRecord
from app.workspaces.models import WorkspaceRecord
from scripts.dataset_manifest import Manifest, Named, digest, operational_id, shared_id
from scripts.seed_support import SeedConfigurationError, require_migration_owner

type OperationalRecord = (
    FacilityRecord | EquipmentUnitRecord | InventoryItemRecord | IncidentRecord | WorkOrderRecord
)

OPERATIONAL: tuple[type[OperationalRecord], ...] = (
    FacilityRecord,
    EquipmentUnitRecord,
    InventoryItemRecord,
    IncidentRecord,
    WorkOrderRecord,
)


def publish(session: Session, manifest: Manifest) -> BaselineRecord:
    """Compare released content rather than upserting shared catalog definitions."""
    # Serialize cooperating publishers, including different baselines on one catalog.
    session.execute(text("SELECT pg_advisory_xact_lock(150015)"))
    catalog = manifest.catalog
    catalog_hash = digest(catalog.model_dump(mode="json"))
    release_id = shared_id(catalog.version, "release", catalog.version)
    release = session.scalar(
        select(CatalogReleaseRecord).where(CatalogReleaseRecord.code == catalog.version)
    )
    existing_release = release is not None
    if release is None:
        release = CatalogReleaseRecord(
            id=release_id, code=catalog.version, content_sha256=catalog_hash
        )
        session.add(release)
        session.flush()
    elif release.id != release_id or release.content_sha256 != catalog_hash:
        raise SeedConfigurationError("Published catalog content differs; create a new release.")
    catalog_records: tuple[
        tuple[str, tuple[Named, ...], type[EquipmentModelRecord] | type[ComponentRecord]], ...
    ] = (
        ("models", catalog.models, EquipmentModelRecord),
        ("components", catalog.components, ComponentRecord),
    )
    for entity, rows, record_type in catalog_records:
        expected = {
            shared_id(catalog.version, entity, row.key): (row.key, row.name) for row in rows
        }
        actual = {
            row_id: (code, name)
            for row_id, code, name in session.execute(
                select(record_type.id, record_type.code, record_type.name).where(
                    record_type.catalog_release_id == release_id
                )
            )
        }
        if existing_release:
            if actual != expected:
                raise SeedConfigurationError(
                    "Published catalog rows were changed, added, or removed."
                )
        else:
            session.add_all(
                [
                    record_type(id=id_, catalog_release_id=release_id, code=code, name=name)
                    for id_, (code, name) in expected.items()
                ]
            )
    session.flush()
    expected_pairs = {
        (
            shared_id(catalog.version, "models", model),
            shared_id(catalog.version, "components", component),
        )
        for model, component in catalog.compatibility
    }
    actual_pairs = set(
        session.execute(
            select(
                equipment_model_components.c.equipment_model_id,
                equipment_model_components.c.component_id,
            ).where(equipment_model_components.c.catalog_release_id == release_id)
        ).tuples()
    )
    if existing_release:
        if actual_pairs != expected_pairs:
            raise SeedConfigurationError("Published catalog compatibility was changed.")
    elif expected_pairs:
        session.execute(
            equipment_model_components.insert(),
            [
                dict(
                    catalog_release_id=release_id, equipment_model_id=model, component_id=component
                )
                for model, component in sorted(expected_pairs)
            ],
        )
    document = manifest.model_dump(mode="json")
    baseline_hash = digest(document)
    baseline_id = shared_id(manifest.version, "baseline", manifest.version)
    baseline = session.scalar(
        select(BaselineRecord).where(BaselineRecord.version == manifest.version)
    )
    if baseline is None:
        baseline = BaselineRecord(
            id=baseline_id,
            version=manifest.version,
            catalog_release_id=release_id,
            content_sha256=baseline_hash,
            manifest=document,
        )
        session.add(baseline)
        session.flush()
    elif (baseline.id, baseline.catalog_release_id, baseline.content_sha256, baseline.manifest) != (
        baseline_id,
        release_id,
        baseline_hash,
        document,
    ):
        raise SeedConfigurationError("Published baseline differs; create a new baseline version.")
    return baseline


def baseline_rows(
    manifest: Manifest, workspace_id: UUID
) -> list[tuple[type[OperationalRecord], list[dict[str, object]]]]:
    def oid(entity: str, key: str | None) -> UUID | None:
        return None if key is None else operational_id(workspace_id, manifest.version, entity, key)

    def common(entity: str, key: str) -> dict[str, object]:
        return dict(
            id=oid(entity, key),
            workspace_id=workspace_id,
            created_at=manifest.created_at,
            updated_at=manifest.created_at,
        )

    facilities = [
        dict(
            **common("facilities", r.key),
            code=r.key,
            name=r.name,
            facility_type=r.facility_type,
            location=r.location,
            operational_status=r.operational_status,
        )
        for r in manifest.facilities
    ]
    units = [
        dict(
            **common("units", r.key),
            facility_id=oid("facilities", r.facility),
            equipment_model_id=shared_id(manifest.catalog.version, "models", r.model),
            asset_tag=r.key,
            operational_status=r.operational_status,
        )
        for r in manifest.units
    ]
    inventory = [
        dict(
            **common("inventory", r.key),
            facility_id=oid("facilities", r.facility),
            component_id=shared_id(manifest.catalog.version, "components", r.component),
            quantity_on_hand=r.quantity_on_hand,
            reorder_point=r.reorder_point,
        )
        for r in manifest.inventory
    ]
    incidents = []
    for r in manifest.incidents:
        values = common("incidents", r.key)
        values.update(
            created_at=r.occurred_at + timedelta(minutes=1),
            updated_at=r.resolved_at or r.occurred_at + timedelta(minutes=1),
        )
        incidents.append(
            dict(
                **values,
                facility_id=oid("facilities", r.facility),
                equipment_unit_id=oid("units", r.unit),
                reference_code=r.key,
                severity=r.severity,
                status=r.status,
                occurred_at=r.occurred_at,
                fault_code=r.fault_code,
                resolved_at=r.resolved_at,
            )
        )
    work = [
        dict(
            **{**common("work_orders", r.key), "updated_at": r.completed_at or manifest.created_at},
            facility_id=oid("facilities", r.facility),
            originating_incident_id=oid("incidents", r.incident),
            target_equipment_unit_id=oid("units", r.target),
            reference_code=r.key,
            priority=r.priority,
            status=r.status,
            due_at=r.due_at,
            completed_at=r.completed_at,
        )
        for r in manifest.work_orders
    ]
    return list(zip(OPERATIONAL, (facilities, units, inventory, incidents, work), strict=True))


def seed_workspace(
    session: Session, workspace_id: UUID, manifest: Manifest, *, refresh: bool = False
) -> dict[str, int]:
    """Create a copy, preserve an existing copy, or explicitly restore its baseline."""
    require_migration_owner(session)
    baseline = publish(session, manifest)
    workspace = session.get(WorkspaceRecord, workspace_id, with_for_update=True)
    new = workspace is None
    if workspace is None:
        workspace = WorkspaceRecord(
            id=workspace_id, baseline_id=baseline.id, catalog_release_id=baseline.catalog_release_id
        )
        session.add(workspace)
        session.flush()
    elif workspace.baseline_id is None:
        if any(
            session.scalar(
                select(func.count()).select_from(record).where(record.workspace_id == workspace_id)
            )
            for record in OPERATIONAL
        ):
            raise SeedConfigurationError(
                "Existing unpinned workspace is not empty; select a new workspace UUID."
            )
        workspace.baseline_id, workspace.catalog_release_id = (
            baseline.id,
            baseline.catalog_release_id,
        )
        session.flush()
        new = True
    elif (
        workspace.baseline_id != baseline.id
        or workspace.catalog_release_id != baseline.catalog_release_id
    ):
        raise SeedConfigurationError(
            "Workspace is pinned; use a new workspace for another baseline."
        )
    if new or refresh:
        if refresh and not new:
            for record in reversed(OPERATIONAL):
                session.execute(delete(record).where(record.workspace_id == workspace_id))
            session.flush()
            session.expire_all()
        for record, values in baseline_rows(manifest, workspace_id):
            session.execute(cast(Table, record.__table__).insert(), values)
        session.flush()
        validate_workspace(session, workspace_id, manifest)
    return {
        record.__tablename__: session.scalar(
            select(func.count()).select_from(record).where(record.workspace_id == workspace_id)
        )
        or 0
        for record in OPERATIONAL
    }


def validate_workspace(session: Session, workspace_id: UUID, manifest: Manifest) -> None:
    """Exact baseline comparison; catches omissions, wrong IDs and broken remapping."""
    for record, expected in baseline_rows(manifest, workspace_id):
        columns = list(expected[0]) if expected else ["id"]
        actual = (
            session.execute(
                select(*(getattr(record, key) for key in columns)).where(
                    record.workspace_id == workspace_id
                )
            )
            .mappings()
            .all()
        )
        if {row["id"]: dict(row) for row in actual} != {row["id"]: row for row in expected}:
            raise SeedConfigurationError(f"Workspace differs from baseline: {record.__tablename__}")
