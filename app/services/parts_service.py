"""Spare-parts stock rules."""
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part import PartTable
from app.schemas.common import utc_now


class PartNotFound(Exception):
    pass


class InsufficientStock(Exception):
    pass


async def adjust_stock(db: AsyncSession, part_id: UUID, quantity_change: int) -> PartTable:
    """Add (restock) or subtract (consume) stock in ONE atomic UPDATE.

    Reading the row, changing it in Python and writing it back is a race: two technicians
    consuming the last part at the same moment would both see stock=1 and both succeed.
    Doing the arithmetic and the "never below zero" check inside a single UPDATE lets
    Postgres serialise concurrent requests on the row lock, so the second one fails cleanly.
    """
    statement = (
        update(PartTable)
        .where(PartTable.id == part_id)
        .where(PartTable.quantity_in_stock + quantity_change >= 0)
        .values(quantity_in_stock=PartTable.quantity_in_stock + quantity_change, updated_at=utc_now())
        .returning(PartTable)
        .execution_options(populate_existing=True)
    )
    part = (await db.execute(statement)).scalar_one_or_none()
    if part is None:
        # No row updated: either the part doesn't exist, or the change would go below zero.
        if await db.get(PartTable, part_id) is None:
            raise PartNotFound()
        raise InsufficientStock("Not enough stock: quantity cannot go below zero")
    await db.commit()
    return part
