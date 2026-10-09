import logging

from backend.auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from services.database import get_db
from services.models import SKU, StockEntry, StockExit
from services.schemas import (
    SKUCreate,
    SKURead,
    SKUSummary,
    StockEntryCreate,
    StockEntryRead,
    StockExitCreate,
    InventoryOrderRead,
    StockExitRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["inventory"])


def _current_stock(session: Session, sku_id: int, warehouse: str) -> int:
    inbound = session.exec(
        select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            StockEntry.sku_id == sku_id,
            StockEntry.warehouse == warehouse,
        )
    ).one()
    outbound = session.exec(
        select(func.coalesce(func.sum(StockExit.quantity), 0)).where(
            StockExit.sku_id == sku_id,
            StockExit.warehouse == warehouse,
        )
    ).one()
    return int(inbound - outbound)


def _sku_response(session: Session, sku: SKU) -> SKURead:
    return SKURead(**sku.model_dump(), current_stock=_current_stock(session, sku.id, sku.warehouse))


def _ensure_sku_warehouse(sku: SKU, warehouse: str) -> None:
    if sku.warehouse != warehouse:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse '{warehouse}' does not match SKU '{sku.sku}' warehouse '{sku.warehouse}'.",
        )


def _log_database_error(operation: str, error: SQLAlchemyError) -> None:
    logger.error("Inventory %s failed (%s)", operation, type(error).__name__)


@router.get("/products", response_model=list[SKURead])
def list_products(
    session: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        products = session.exec(select(SKU).order_by(SKU.id)).all()
        inbound_rows = session.exec(
            select(StockEntry.sku_id, StockEntry.warehouse, func.sum(StockEntry.quantity)).group_by(
                StockEntry.sku_id, StockEntry.warehouse
            )
        ).all()
        outbound_rows = session.exec(
            select(StockExit.sku_id, StockExit.warehouse, func.sum(StockExit.quantity)).group_by(
                StockExit.sku_id, StockExit.warehouse
            )
        ).all()
    except SQLAlchemyError as error:
        _log_database_error("product listing", error)
        raise HTTPException(status_code=500, detail="Products could not be loaded. Please retry.") from None

    inbound = {(sku_id, warehouse): int(quantity or 0) for sku_id, warehouse, quantity in inbound_rows}
    outbound = {(sku_id, warehouse): int(quantity or 0) for sku_id, warehouse, quantity in outbound_rows}
    return [
        SKURead(
            **product.model_dump(),
            current_stock=inbound.get((product.id, product.warehouse), 0)
            - outbound.get((product.id, product.warehouse), 0),
        )
        for product in products
    ]


@router.post("/products", response_model=SKURead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: SKUCreate,
    session: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    product = SKU(**payload.model_dump())
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A SKU with this code already exists in that warehouse.",
        ) from None
    except SQLAlchemyError as error:
        session.rollback()
        _log_database_error("product creation", error)
        raise HTTPException(status_code=500, detail="Product could not be created. Please retry.") from None
    return SKURead(**product.model_dump(), current_stock=0)


@router.get("/products/{product_id}", response_model=SKURead)
def get_product(
    product_id: int,
    session: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        product = session.get(SKU, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="SKU not found.")
        return _sku_response(session, product)
    except SQLAlchemyError as error:
        _log_database_error("product lookup", error)
        raise HTTPException(status_code=500, detail="Product could not be loaded. Please retry.") from None


@router.post("/orders/inbound", response_model=StockEntryRead, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    payload: StockEntryCreate,
    session: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        product = session.get(SKU, payload.sku_id)
        if product is None:
            raise HTTPException(status_code=404, detail="SKU not found.")
        _ensure_sku_warehouse(product, payload.warehouse)
        entry = StockEntry(**payload.model_dump(), user_uuid=user["id"])
        session.add(entry)
        session.commit()
        session.refresh(entry)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="This inbound reference already exists for that warehouse.") from None
    except SQLAlchemyError as error:
        session.rollback()
        _log_database_error("inbound order", error)
        raise HTTPException(status_code=500, detail="Inbound order could not be saved. Please retry.") from None
    return StockEntryRead(**entry.model_dump(), sku=SKUSummary.model_validate(product))


@router.post("/orders/outbound", response_model=StockExitRead, status_code=status.HTTP_201_CREATED)
def create_outbound_order(
    payload: StockExitCreate,
    session: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        product = session.exec(
            select(SKU).where(SKU.id == payload.sku_id).with_for_update()
        ).first()
        if product is None:
            raise HTTPException(status_code=404, detail="SKU not found.")
        _ensure_sku_warehouse(product, payload.warehouse)
        available = _current_stock(session, payload.sku_id, payload.warehouse)
        if payload.quantity > available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for SKU '{product.sku}'. "
                    f"Available: {available}, requested: {payload.quantity}."
                ),
            )

        exit_record = StockExit(**payload.model_dump(), user_uuid=user["id"])
        session.add(exit_record)
        session.commit()
        session.refresh(exit_record)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Outbound order could not be recorded for this SKU.") from None
    except SQLAlchemyError as error:
        session.rollback()
        _log_database_error("outbound order", error)
        raise HTTPException(status_code=500, detail="Outbound order could not be saved. Please retry.") from None
    return StockExitRead(**exit_record.model_dump(), sku=SKUSummary.model_validate(product))


@router.get("/orders", response_model=list[InventoryOrderRead])
def list_orders(
    session: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        inbound = session.exec(
            select(StockEntry, SKU)
            .join(SKU, StockEntry.sku_id == SKU.id)
            .order_by(StockEntry.created_at.desc(), StockEntry.id.desc())
        ).all()
        outbound = session.exec(
            select(StockExit, SKU)
            .join(SKU, StockExit.sku_id == SKU.id)
            .order_by(StockExit.created_at.desc(), StockExit.id.desc())
        ).all()
    except SQLAlchemyError as error:
        _log_database_error("order listing", error)
        raise HTTPException(status_code=500, detail="Orders could not be loaded. Please retry.") from None

    orders: list[InventoryOrderRead] = []
    for entry, product in inbound:
        orders.append(
            InventoryOrderRead(
                movement_type="inbound",
                id=entry.id,
                sku_id=entry.sku_id,
                quantity=entry.quantity,
                warehouse=entry.warehouse,
                created_at=entry.created_at,
                user_uuid=entry.user_uuid,
                sku=SKUSummary.model_validate(product),
                reference=entry.reference,
            )
        )
    for exit_record, product in outbound:
        orders.append(
            InventoryOrderRead(
                movement_type="outbound",
                id=exit_record.id,
                sku_id=exit_record.sku_id,
                quantity=exit_record.quantity,
                warehouse=exit_record.warehouse,
                created_at=exit_record.created_at,
                user_uuid=exit_record.user_uuid,
                sku=SKUSummary.model_validate(product),
                exit_type=exit_record.exit_type,
                tracking_number=exit_record.tracking_number,
            )
        )
    orders.sort(key=lambda order: (order.created_at, order.id), reverse=True)
    return orders
