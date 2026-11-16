"""Load a realistic demo plant: users, machines, maintenance history, issues, parts and manuals.

    docker compose exec app python -m app.seed_demo

Idempotent: anything that already exists (same username, serial number or document title) is skipped,
and an existing user's password is never changed. Dates are relative to today, so "due in 30 days"
and "overdue" always mean something.

DEMO USE ONLY. The supervisor and technician accounts below have fixed, published passwords so anyone
trying the app can sign in. Never run this against a database that holds real data.

On a public deployment, set DEMO_ADMIN_PASSWORD when seeding: the admin account then gets that private
password instead of the published one, so visitors can't delete data or manage users.
"""
import asyncio
import os
import pathlib
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import select

from app.core.database import async_session_maker, engine
from app.models.document import DocumentFileTable, DocumentTable
from app.models.equipment import EquipmentTable
from app.models.issue import IssueTable
from app.models.maintenance import MaintenanceTable
from app.models.part import PartTable
from app.models.user import UserTable
from app.schemas.equipment import STATUS as EquipmentStatus
from app.schemas.issue import STATUS as IssueStatus
from app.services.auth_service import hash_password
from app.services.documents_service import index_document

MANUALS = pathlib.Path(__file__).resolve().parent.parent / "sample_data" / "manuals"

# username, email, role, password (demo only, see module docstring)
DEMO_USERS = [
    ("priya", "priya@plant.test", "admin", "AdminPass123"),
    ("maria", "maria@plant.test", "supervisor", "SupPass123"),
    ("ravi", "ravi@plant.test", "technician", "TechPass123"),
    ("jlee", "jlee@plant.test", "technician", "TechPass123"),
]

# name, serial, type, model, location, department, status, purchased (years ago), manual stem
MACHINES = [
    ("Northfield TL-300 CNC Lathe", "NF-TL300-0001", "CNC Machine", "TL-300", "Bay 3", "Machining",
     "under maintenance", 4, "northfield_tl300_lathe"),
    ("Northfield SP-800 Press", "NF-SP800-0002", "Stamping Press", "SP-800", "Line 2", "Stamping",
     "active", 6, "northfield_sp800_press"),
    ("Northfield AC-55 Compressor", "NF-AC55-0003", "Air Compressor", "AC-55", "Utilities room", "Facilities",
     "active", 2, "northfield_ac55_compressor"),
    ("Welding Robot WR-12", "WR12-4471", "Welding Robot", "WR-12", "Cell 4", "Body Shop", "active", 3, None),
    ("Paint Robot PR-7", "PR7-2290", "Paint Robot", "PR-7", "Booth 1", "Paint Shop", "active", 5, None),
    ("Conveyor CV-09", "CV09-1180", "Conveyor", "CV-09", "Line 1", "General Assembly", "active", 8, None),
    ("Laser Cutter LC-5", "LC5-3302", "Laser Cutter", "LC-5", "Bay 5", "Fabrication", "active", 2, None),
    ("Vision System VS-2", "VS2-0815", "Vision System", "VS-2", "End of line", "Quality", "active", 1, None),
    ("Forklift FL-21", "FL21-6610", "Forklift", "FL-21", "Warehouse", "Logistics", "under maintenance", 7, None),
    ("Boiler B-1", "B1-1999", "Boiler", "B-1", "Utilities room", "Facilities", "retired", 20, None),
]

# serial, log type, days ago, next service in days (None = none), duration min, cost, description, by
LOGS = [
    ("NF-TL300-0001", "Scheduled", 40, 25, 120, 450.0, "Slideway lubrication and chuck jaw greasing", "ravi"),
    ("NF-TL300-0001", "Corrective", 3, 30, 90, 180.0, "Reseated spindle encoder cable after E-47 alarm", "ravi"),
    ("NF-SP800-0002", "Inspection", 75, -6, 60, 0.0, "Two-hand control and ram drift test", "jlee"),
    ("NF-AC55-0003", "Scheduled", 20, 70, 45, 120.0, "Intake filter change, condensate drain check", "jlee"),
    ("WR12-4471", "Calibration", 30, 12, 75, 300.0, "Tool centre point calibration", "ravi"),
    ("PR7-2290", "Cleaning", 220, None, 120, 90.0, "Nozzle and line flush", "jlee"),
    ("CV09-1180", "Scheduled", 15, 9, 60, 75.0, "Belt tension and roller bearing check", "ravi"),
    ("LC5-3302", "Inspection", 10, 50, 30, 0.0, "Lens and nozzle inspection", "jlee"),
    ("VS2-0815", "Software Update", 5, 85, 20, 0.0, "Inspection recipe update", "ravi"),
    ("FL21-6610", "Corrective", 1, 14, 180, 640.0, "Hydraulic mast seal replacement", "jlee"),
]

# serial, title, severity, status, error code, reporter, assignee, days ago, description
ISSUES = [
    ("NF-TL300-0001", "Spindle vibration above 3000 RPM", "Critical", "In Progress", "E-47", "jlee", "ravi", 2,
     "E-47 alarm with audible vibration at high speed after the weekend shutdown."),
    ("NF-SP800-0002", "Hydraulic oil running hot", "High", "Open", "H-21", "ravi", None, 1,
     "H-21 appeared twice on second shift; cooler fan seems slow."),
    ("WR12-4471", "Weld spatter increasing on seam 3", "Medium", "Open", None, "jlee", None, 4,
     "Spatter on the left door seam has doubled since Monday."),
    ("CV09-1180", "Belt tracking off-centre", "Low", "Resolved", None, "ravi", "ravi", 6,
     "Belt drifting toward the guard; retensioned."),
    ("LC5-3302", "Cut edge burr on 3 mm steel", "Medium", "Closed", None, "jlee", "jlee", 12,
     "Burr fixed by replacing the nozzle."),
    ("PR7-2290", "Paint flow fluctuates", "High", "Open", None, "ravi", None, 0,
     "Flow meter readings swing by 15 percent during the colour change."),
]

# serial, part name, part number, quantity, reorder threshold, unit cost, supplier
PARTS = [
    ("NF-TL300-0001", "Spindle encoder cable", "TL-ENC-04", 1, 2, 85.0, "Northfield Parts"),
    ("NF-TL300-0001", "Chuck jaw set", "TL-JAW-10", 4, 1, 220.0, "Northfield Parts"),
    ("NF-SP800-0002", "Return-line filter element", "SP-FLT-22", 2, 2, 64.0, "Northfield Parts"),
    ("NF-AC55-0003", "Air intake filter", "AC-AIF-05", 6, 2, 38.0, "Northfield Parts"),
    ("NF-AC55-0003", "Synthetic compressor oil NF-46 (5 L)", "AC-OIL-46", 0, 2, 72.0, "Northfield Parts"),
    ("WR12-4471", "Contact tips (pack of 25)", "WR-CT-25", 9, 3, 41.0, "WeldSupply Co"),
    ("CV09-1180", "Roller bearing 6204", "BRG-6204", 12, 4, 7.5, "BearingHub"),
    ("FL21-6610", "Mast hydraulic seal kit", "FL-SEAL-21", 1, 1, 130.0, "LiftParts"),
]


def at(days_ago: float) -> datetime:
    """A UTC timestamp at 09:00 `days_ago` days before today (negative = in the future)."""
    day = date.today() - timedelta(days=days_ago)
    return datetime.combine(day, time(9, 0), tzinfo=timezone.utc)


async def seed() -> None:
    async with async_session_maker() as db:
        users = {u.username: u for u in (await db.execute(select(UserTable))).scalars()}
        for username, email, role, password in DEMO_USERS:
            if role == "admin":
                password = os.environ.get("DEMO_ADMIN_PASSWORD") or password
            if username not in users:
                users[username] = UserTable(username=username, email=email, role=role,
                                            hashed_password=hash_password(password))
                db.add(users[username])
        await db.flush()

        machines = {m.serial_number: m for m in (await db.execute(select(EquipmentTable))).scalars()}
        created = set()
        for name, serial, kind, model, location, dept, status, years, _ in MACHINES:
            if serial not in machines:
                purchased = date.today() - timedelta(days=365 * years)
                machines[serial] = EquipmentTable(
                    name=name, serial_number=serial, equipment_type=kind, model_number=model, location=location,
                    department=dept, status=EquipmentStatus(status), purchased_at=purchased,
                    warranty_expires_at=purchased + timedelta(days=365 * 5))
                db.add(machines[serial])
                created.add(serial)
        await db.flush()

        # History, issues and parts only for machines this run created, so re-running adds no duplicates.
        for serial, kind, ago, next_in, minutes, cost, text, by in LOGS:
            if serial in created:
                db.add(MaintenanceTable(
                    equipment_id=machines[serial].id, log_type=kind, performed_at=at(ago), description=text,
                    duration_minutes=minutes, cost_usd=cost, performed_by=by, performed_by_id=users[by].id,
                    next_scheduled_at=at(-next_in) if next_in is not None else None, created_at=at(ago)))
        for serial, title, severity, status, code, reporter, assignee, ago, text in ISSUES:
            if serial in created:
                done = status in ("Resolved", "Closed")
                db.add(IssueTable(
                    equipment_id=machines[serial].id, title=title, description=text, severity=severity,
                    status=IssueStatus(status), error_code=code, reported_by=reporter,
                    reported_by_id=users[reporter].id, assigned_to=assignee,
                    assigned_to_id=users[assignee].id if assignee else None, created_at=at(ago),
                    updated_at=at(max(ago - 1, 0)), resolved_at=at(max(ago - 1, 0)) if done else None))
        for serial, name, number, qty, threshold, cost, supplier in PARTS:
            if serial in created:
                db.add(PartTable(equipment_id=machines[serial].id, part_name=name, part_number=number,
                                 quantity_in_stock=qty, reorder_threshold=threshold, unit_cost_usd=cost,
                                 supplier=supplier))
        await db.commit()

        existing_titles = set((await db.execute(select(DocumentTable.title))).scalars())
        owner = {machine[-1]: machines[machine[1]].id for machine in MACHINES if machine[-1]}
        new_documents = []
        for path in sorted(MANUALS.glob("*.md")) if MANUALS.exists() else []:
            title = path.read_text().splitlines()[0].lstrip("# ").split(":")[0][:100]
            if title in existing_titles:
                continue
            content = path.read_bytes()
            document = DocumentTable(
                title=title, doc_type="Service Manual" if path.stem in owner else "Lockout/Tagout Procedure",
                equipment_id=owner.get(path.stem), blob_url="", file_size_bytes=len(content),
                content_type="text/markdown", uploaded_by="maria", uploaded_by_id=users["maria"].id)
            document.blob_url = f"/api/v1/documents/{document.id}/file"
            db.add(document)
            await db.flush()  # the file row references the document, so insert the document first
            db.add(DocumentFileTable(document_id=document.id, content=content))
            new_documents.append(document.id)
        await db.commit()

    for document_id in new_documents:
        await index_document(async_session_maker, document_id)
    await engine.dispose()
    print(f"Seeded: {len(created)} machines, {len(new_documents)} manuals; demo users: "
          + ", ".join(f"{u} ({r})" for u, _, r, _ in DEMO_USERS))
    if not MANUALS.exists():
        print("Note: sample_data/manuals not found, so no manuals were loaded.")


if __name__ == "__main__":
    asyncio.run(seed())
