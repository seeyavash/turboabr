import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaymentMethod
from app.integrations.payments import NowPaymentsClient, PaymentProviderError, PlisioClient
from app.services.payments import PaymentService
from app.services.settings import SettingsService

logger = logging.getLogger(__name__)


async def verify_crypto_payments(session: AsyncSession) -> None:
    service = PaymentService(session)
    settings = SettingsService(session)
    for payment in await service.pending_provider_payments():
        try:
            if payment.method == PaymentMethod.plisio.value:
                token = await settings.get("plisio_api_token")
                paid = await PlisioClient(token or "").is_paid(payment.provider_invoice_id or "")
            else:
                token = await settings.get("nowpayments_api_token")
                paid = await NowPaymentsClient(token or "").is_paid(payment.provider_invoice_id or "")
            if paid:
                await service.approve(payment, "تایید خودکار توسط درگاه پرداخت")
        except PaymentProviderError:
            logger.exception("Payment provider verification failed for payment %s", payment.id)
