import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, get_current_user_claims
from app.core.security import UserRole
from app.database.connection import get_db
from app.schemas.notification import NotificationType
from app.schemas.selling_request import SellingRequestStatus
from app.schemas.transaction import (
    PaymentStatus,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionStatus,
    TransactionStatusUpdate,
)
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.notification_service import (
    NotificationRepository,
    dispatch_in_app_notification,
    get_notification_repo,
)
from app.services.trade_service import (
    SellingRequestRepository,
    get_selling_request_repo,
)
from app.services.transaction_service import (
    TransactionRepository,
    TransactionWorkflowError,
    get_transaction_repo,
)

router = APIRouter(prefix="/transactions", tags=["Digital Transactions"])


def _record_value(record, field: str, default=None):
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create digital transaction from accepted selling request",
)
def create_digital_transaction(
    req_in: TransactionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    selling_req_repo: SellingRequestRepository = Depends(get_selling_request_repo),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Creates a verified digital trade record and settlement receipt from an accepted selling request.
    - Validates that the selling request is in ACCEPTED status.
    - Verifies that the authenticated user is either the requesting farmer or the accepting buyer.
    - Prevents duplicate transaction records for the same accepted selling request.
    - Applies existing price, deductions, and net-realization calculations.
    - Initializes trade in CONFIRMED status with PENDING payment.
    """
    try:
        # Retrieve selling request
        selling_request = selling_req_repo.get_request_by_id(db, req_in.selling_request_id)
        if not selling_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selling request with ID {req_in.selling_request_id} not found.",
            )

        # Enforce that selling request is in ACCEPTED status
        req_status = _record_value(selling_request, "status")
        if req_status != SellingRequestStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create transaction: Selling request is in '{req_status}' status. Only ACCEPTED requests can be transacted.",
            )

        # Enforce ownership: only participant farmer or buyer can generate transaction
        req_farmer_id = _record_value(selling_request, "farmer_id")
        req_buyer_id = _record_value(selling_request, "buyer_id")
        if current_user.id not in (req_farmer_id, req_buyer_id) and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to create a transaction for this trade agreement.",
            )

        # Duplicate transaction prevention
        existing_txn = trans_repo.get_by_selling_request_id(db, req_in.selling_request_id)
        if existing_txn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A digital transaction ({_record_value(existing_txn, 'transaction_id')}) has already been generated for this selling request.",
            )

        # Create transaction record
        created_txn = trans_repo.create_transaction(
            db,
            selling_request=selling_request,
            payment_method=req_in.payment_method,
            notes=req_in.notes,
        )

        # Dispatch in-app notifications to both parties
        created_code = _record_value(created_txn, "transaction_id")
        created_crop = _record_value(created_txn, "crop_name")
        created_quantity = _record_value(created_txn, "quantity")
        created_unit = _record_value(created_txn, "quantity_unit")
        dispatch_in_app_notification(
            db=db,
            notification_repo=notif_repo,
            user_id=req_farmer_id,
            notification_type=NotificationType.TRANSACTION_CREATED,
            title="Digital Trade Receipt Generated",
            message=f"Transaction {created_code} generated for {created_crop} ({created_quantity} {created_unit}).",
            reference_id=created_code,
        )
        dispatch_in_app_notification(
            db=db,
            notification_repo=notif_repo,
            user_id=req_buyer_id,
            notification_type=NotificationType.TRANSACTION_CREATED,
            title="Digital Trade Receipt Generated",
            message=f"Transaction {created_code} generated for purchase of {created_crop} ({created_quantity} {created_unit}).",
            reference_id=created_code,
        )

        return created_txn

    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database transactions schema is pending approval by Ankita: {str(e)}",
        )
    except TransactionWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List digital transactions for the authenticated user",
)
def list_user_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
):
    """
    Retrieves all digital transactions associated with the authenticated farmer or buyer.
    Admins can view transactions via the /admin/transactions route.
    """
    try:
        user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        items, total = trans_repo.list_user_transactions(
            db, user_id=current_user.id, role=user_role_str, skip=skip, limit=limit
        )
        return TransactionListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database transactions schema is pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve digital trade receipt by ID",
)
def get_transaction_by_id(
    transaction_id: int = Path(..., ge=1, description="Transaction ID"),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
):
    """
    Retrieves complete digital receipt details for a transaction.
    Enforces privacy: Only the involved farmer, buyer, or system administrators can view the receipt.
    """
    try:
        txn = trans_repo.get_transaction_by_id(db, transaction_id)
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID {transaction_id} not found.",
            )

        # Authorization check
        is_participant = current_user.id in (
            _record_value(txn, "farmer_id"), _record_value(txn, "buyer_id")
        )
        is_admin = current_user.role == UserRole.ADMIN
        if not is_participant and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this transaction receipt.",
            )

        return txn
    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database transactions schema is pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/{transaction_id}/receipt",
    status_code=status.HTTP_200_OK,
    summary="Download transaction trade receipt as server-side generated PDF",
)
def download_transaction_pdf_receipt(
    transaction_id: int = Path(..., ge=1, description="Transaction ID"),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
):
    """
    Generates and streams a formal PDF agricultural settlement receipt.
    Enforces privacy: accessible only by involved farmer, buyer, or system administrators.
    """
    try:
        txn = trans_repo.get_transaction_by_id(db, transaction_id)
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID {transaction_id} not found.",
            )

        is_participant = current_user.id in (
            _record_value(txn, "farmer_id"), _record_value(txn, "buyer_id")
        )
        is_admin = current_user.role == UserRole.ADMIN
        if not is_participant and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to download this transaction receipt.",
            )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#065F46"),
            alignment=1,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4B5563"),
            alignment=1,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=10,
            spaceAfter=4,
        )
        normal_style = styles["Normal"]

        elements = []

        elements.append(Paragraph("FarmerLinkage — Agricultural Trade Receipt", title_style))
        elements.append(Paragraph("Smart India Hackathon SIH26132 • Certified Digital Mandi Settlement", subtitle_style))
        elements.append(Spacer(1, 15))

        txn_code = _record_value(txn, "transaction_id", f"TXN-{transaction_id}")
        req_code = _record_value(txn, "request_code", "N/A")
        created_at_val = _record_value(txn, "created_at")
        date_str = created_at_val.strftime("%Y-%m-%d %H:%M UTC") if hasattr(created_at_val, "strftime") else str(created_at_val or "N/A")

        meta_data = [
            [Paragraph("<b>Receipt Reference:</b>", normal_style), Paragraph(str(txn_code), normal_style)],
            [Paragraph("<b>Agreement Code:</b>", normal_style), Paragraph(str(req_code), normal_style)],
            [Paragraph("<b>Settlement Date:</b>", normal_style), Paragraph(date_str, normal_style)],
            [Paragraph("<b>Trade Status:</b>", normal_style), Paragraph(str(_enum_value(_record_value(txn, "transaction_status"))), normal_style)],
            [Paragraph("<b>Payment Status:</b>", normal_style), Paragraph(str(_enum_value(_record_value(txn, "payment_status"))), normal_style)],
        ]
        meta_table = Table(meta_data, colWidths=[150, 350])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Trade Counterparties", section_style))
        farmer_name = _record_value(txn, "farmer_name", f"Farmer #{_record_value(txn, 'farmer_id')}")
        buyer_name = _record_value(txn, "buyer_name", f"Buyer #{_record_value(txn, 'buyer_id')}")
        parties_data = [
            [Paragraph("<b>Producer / Farmer:</b>", normal_style), Paragraph(str(farmer_name), normal_style)],
            [Paragraph("<b>Procuring Buyer:</b>", normal_style), Paragraph(str(buyer_name), normal_style)],
        ]
        parties_table = Table(parties_data, colWidths=[150, 350])
        parties_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(parties_table)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Produce & Financial Breakdown", section_style))
        crop_name = _record_value(txn, "crop_name", "Produce")
        qty = _record_value(txn, "quantity", 0)
        qty_unit = _record_value(txn, "quantity_unit", "quintal")
        price = float(_record_value(txn, "agreed_price", _record_value(txn, "agreed_price_per_unit", 0)))
        price_unit = _record_value(txn, "price_unit", "INR/quintal")
        gross = float(_record_value(txn, "gross_amount", 0))
        transport = float(_record_value(txn, "transport_cost", 0))
        other = float(_record_value(txn, "other_charges", 0))
        net = float(_record_value(txn, "net_amount", 0))
        pay_method = _record_value(txn, "payment_method") or "DIRECT_BANK_TRANSFER"

        financial_data = [
            [Paragraph("<b>Crop Commodity</b>", normal_style), Paragraph(str(crop_name), normal_style)],
            [Paragraph("<b>Quantity Transacted</b>", normal_style), Paragraph(f"{qty} {qty_unit}", normal_style)],
            [Paragraph("<b>Agreed Price per Unit</b>", normal_style), Paragraph(f"₹{price:,.2f} ({price_unit})", normal_style)],
            [Paragraph("<b>Gross Traded Value</b>", normal_style), Paragraph(f"₹{gross:,.2f}", normal_style)],
            [Paragraph("<b>Transport Adjustment</b>", normal_style), Paragraph(f"- ₹{transport:,.2f}", normal_style)],
            [Paragraph("<b>Mandi Cesses / Other Charges</b>", normal_style), Paragraph(f"- ₹{other:,.2f}", normal_style)],
            [Paragraph("<b>Net Realization / Payable</b>", normal_style), Paragraph(f"<b>₹{net:,.2f}</b>", normal_style)],
            [Paragraph("<b>Settlement Mechanism</b>", normal_style), Paragraph(str(pay_method), normal_style)],
        ]
        financial_table = Table(financial_data, colWidths=[200, 300])
        financial_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 6), (1, 6), colors.HexColor("#ECFDF5")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(financial_table)
        elements.append(Spacer(1, 20))

        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=styles["Italic"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6B7280"),
            alignment=1,
        )
        elements.append(Paragraph("This document serves as a verified electronic transaction record under FarmerLinkage. Not a negotiable instrument.", disclaimer_style))

        doc.build(elements)
        buffer.seek(0)

        filename = f"receipt_{txn_code}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to generate PDF receipt: {str(e)}",
        )


@router.put(
    "/{transaction_id}/status",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transaction fulfillment or settlement status",
)
def update_transaction_status(
    status_update: TransactionStatusUpdate,
    transaction_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Updates the trade fulfillment (CONFIRMED -> IN_TRANSIT -> DELIVERED -> COMPLETED)
    or settlement status (PENDING -> PAYMENT_INITIATED -> ESCROW_HELD -> PAID).
    Enforces valid state transitions and authorization.
    """
    try:
        txn = trans_repo.get_transaction_by_id(db, transaction_id)
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID {transaction_id} not found.",
            )

        # Enforce role-based rights on status updates
        is_farmer = current_user.id == _record_value(txn, "farmer_id")
        is_buyer = current_user.id == _record_value(txn, "buyer_id")
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_farmer or is_buyer or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this transaction.",
            )

        # Role-specific update restrictions
        if is_farmer and not is_admin:
            if status_update.payment_status is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Farmers cannot unilaterally mark payment settlement status.",
                )
            if status_update.transaction_status not in (TransactionStatus.IN_TRANSIT, None):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Farmers can only update transaction status to IN_TRANSIT.",
                )

        if is_buyer and not is_admin:
            allowed_buyer_pay = (PaymentStatus.PAYMENT_INITIATED, PaymentStatus.ESCROW_HELD, None)
            if status_update.payment_status not in allowed_buyer_pay:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Buyers can only initiate payment or deposit escrow.",
                )
            allowed_buyer_trans = (TransactionStatus.DELIVERED, TransactionStatus.COMPLETED, None)
            if status_update.transaction_status not in allowed_buyer_trans:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Buyers can only mark shipments as DELIVERED or COMPLETED.",
                )

        updated_txn = trans_repo.update_transaction_status(db, transaction_id, status_update)

        # Dispatch notification to counterparty
        recipient_id = _record_value(txn, "buyer_id") if is_farmer else _record_value(txn, "farmer_id")
        if recipient_id:
            updated_code = _record_value(updated_txn, "transaction_id")
            dispatch_in_app_notification(
                db=db,
                notification_repo=notif_repo,
                user_id=recipient_id,
                notification_type=NotificationType.TRANSACTION_STATUS,
                title="Transaction Status Updated",
                message=(
                    f"Transaction {updated_code} updated: "
                    f"status={_enum_value(_record_value(updated_txn, 'transaction_status'))}, "
                    f"payment={_enum_value(_record_value(updated_txn, 'payment_status'))}."
                ),
                reference_id=updated_code,
            )

        return updated_txn

    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database transactions schema is pending approval by Ankita: {str(e)}",
        )
    except TransactionWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
