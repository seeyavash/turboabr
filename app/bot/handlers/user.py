from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import payment_methods, plan_detail_actions, receipt_button, service_actions, service_types
from app.core.config import settings as env_settings
from app.db.models import PaymentMethod, PaymentRequest, PaymentStatus, ProductPlan, ServiceStatus, TransactionKind, User, VpnService
from app.integrations.pasarguard import PasarGuardError
from app.services.notifications import send_supergroup_message, send_supergroup_photo
from app.services.catalog import CatalogService
from app.services.menu import MenuService
from app.services.payments import PaymentService
from app.services.services import VpnServiceManager
from app.services.settings import SettingsService
from app.services.users import UserService
from app.services.wallet import WalletService

router = Router()


def status_label(status: str) -> str:
    return {
        ServiceStatus.active.value: "فعال",
        ServiceStatus.disabled.value: "غیرفعال",
        ServiceStatus.deleted.value: "حذف‌شده",
    }.get(status, status)


class ChargeWallet(StatesGroup):
    amount = State()
    receipt = State()


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession) -> None:
    referral_code = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split()) > 1 else None
    existed = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
    user = await UserService(session).get_or_create(message.from_user, referral_code)
    is_new_user = bool(getattr(user, "_was_created", not existed))
    if is_new_user:
        await send_supergroup_message(
            session,
            message.bot,
            "users",
            f"کاربر جدید وارد ربات شد\n"
            f"نام: {user.full_name or '-'}\n"
            f"یوزرنیم: @{user.username or '-'}\n"
            f"آیدی عددی: {user.telegram_id}",
        )
    await message.answer(
        f"خوش آمدید.\nموجودی کیف پول: {user.wallet_balance_toman:,} تومان",
        reply_markup=await MenuService(session).reply_markup(),
    )


async def buy_service(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    if user.is_blocked:
        await message.answer("حساب شما مسدود شده است.")
        return
    plans = await CatalogService(session).active_plans()
    if not plans:
        await message.answer("فعلاً هیچ تعرفه‌ای برای خرید فعال نیست. لطفاً با پشتیبانی تماس بگیرید.")
        return
    await message.answer("تعرفه موردنظر را انتخاب کنید:", reply_markup=service_types(plans))


@router.callback_query(F.data.startswith("buy_plan:"))
async def buy_plan_selected(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(callback.from_user)
    if user.is_blocked:
        await callback.answer("حساب شما مسدود شده است.", show_alert=True)
        return
    plan_id = int(callback.data.split(":", 1)[1])
    plan = await session.get(ProductPlan, plan_id)
    if not plan or not plan.is_active:
        await callback.answer("تعرفه پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_text(
        f"{plan.name}\n\n"
        f"{plan.description or 'توضیحاتی برای این سرویس ثبت نشده است.'}\n\n"
        f"قیمت هر گیگ: {plan.price_per_gb_toman:,} تومان",
        reply_markup=plan_detail_actions(plan.id),
    )
    await callback.answer()


@router.callback_query(F.data == "buy_plans_back")
async def buy_plans_back(callback: CallbackQuery, session: AsyncSession) -> None:
    plans = await CatalogService(session).active_plans()
    await callback.message.edit_text("تعرفه موردنظر را انتخاب کنید:", reply_markup=service_types(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("buy_plan_confirm:"))
async def buy_plan_confirmed(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(callback.from_user)
    if user.is_blocked:
        await callback.answer("حساب شما مسدود شده است.", show_alert=True)
        return
    plan_id = int(callback.data.split(":", 1)[1])
    plan = await session.get(ProductPlan, plan_id)
    if not plan or not plan.is_active:
        await callback.answer("تعرفه پیدا نشد.", show_alert=True)
        return
    panel = await CatalogService(session).client_for_panel(plan.panel_id)
    try:
        service = await VpnServiceManager(session, panel).create_paid_plan(user, plan)
    except PasarGuardError as exc:
        await callback.message.answer(f"خطا در ساخت سرویس:\n{exc}")
        await send_supergroup_message(
            session,
            callback.bot,
            "errors",
            f"خطا در ساخت سرویس\nکاربر: {user.telegram_id}\nتعرفه: {plan.name}\nخطا: {exc}",
        )
        await callback.answer()
        return
    except ValueError as exc:
        await callback.message.answer(str(exc))
        await callback.answer()
        return
    except Exception as exc:
        await callback.message.answer("خطای غیرمنتظره در ساخت سرویس. لطفاً با پشتیبانی تماس بگیرید.")
        await send_supergroup_message(
            session,
            callback.bot,
            "errors",
            f"خطای غیرمنتظره در ساخت سرویس\nکاربر: {user.telegram_id}\nتعرفه: {plan.name}\nخطا: {exc}",
        )
        await callback.answer()
        return
    await send_supergroup_message(
        session,
        callback.bot,
        "orders",
        f"سرویس جدید ساخته شد\n"
        f"کاربر: {user.full_name or '-'}\n"
        f"آیدی عددی: {user.telegram_id}\n"
        f"تعرفه: {plan.name}\n"
        f"نام اکانت: {service.pasarguard_username}",
    )
    await callback.message.answer(f"سرویس شما ساخته شد.\nلینک اشتراک:\n{service.subscription_url}")
    await callback.answer()


async def test_account(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    if user.is_blocked:
        await message.answer("حساب شما مسدود شده است.")
        return
    settings = SettingsService(session)
    if not await settings.get_bool("test_account_enabled", True):
        await message.answer("اکانت تست فعلاً غیرفعال است.")
        return
    test_panel_id = await settings.get("test_panel_id", "")
    panel_id = int(test_panel_id) if test_panel_id else None
    if panel_id is None:
        panels = await CatalogService(session).active_panels()
        panel_id = panels[0].id if panels else None
    if panel_id is None:
        await message.answer("فعلاً پنل PasarGuard تنظیم نشده است. لطفاً با پشتیبانی تماس بگیرید.")
        return
    try:
        panel = await CatalogService(session).client_for_panel(panel_id)
        service = await VpnServiceManager(session, panel).create_test_service(user)
    except PasarGuardError as exc:
        await message.answer(f"خطا در ساخت اکانت تست:\n{exc}")
        await send_supergroup_message(
            session,
            message.bot,
            "errors",
            f"خطا در ساخت اکانت تست\nکاربر: {user.telegram_id}\nخطا: {exc}",
        )
        return
    except Exception as exc:
        await message.answer(str(exc))
        return
    await send_supergroup_message(
        session,
        message.bot,
        "orders",
        f"اکانت تست ساخته شد\n"
        f"کاربر: {user.full_name or '-'}\n"
        f"آیدی عددی: {user.telegram_id}\n"
        f"نام اکانت: {service.pasarguard_username}",
    )
    await message.answer(f"اکانت تست شما فعال شد: ۱۰۰ مگابایت، ۱ روز.\n{service.subscription_url}")


async def my_services(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    result = await session.execute(
        select(VpnService).where(VpnService.user_id == user.id, VpnService.status != ServiceStatus.deleted.value)
    )
    services = list(result.scalars())
    if not services:
        await message.answer("هنوز سرویسی ندارید.")
        return
    for service in services:
        await message.answer(
            f"سرویس #{service.id}\n"
            f"نوع: {service.type}\n"
            f"وضعیت: {status_label(service.status)}\n"
            f"ترافیک محاسبه‌شده: {service.total_billed_mb} مگابایت\n"
            f"{service.subscription_url or ''}",
            reply_markup=service_actions(service.id, service.status == ServiceStatus.disabled.value),
        )


@router.callback_query(F.data.startswith("svc_reactivate:"))
async def reactivate_service(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(callback.from_user)
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if not service or service.user_id != user.id:
        await callback.answer("سرویس پیدا نشد.", show_alert=True)
        return
    if user.wallet_balance_toman <= 0:
        await callback.answer("ابتدا کیف پول خود را شارژ کنید.", show_alert=True)
        return
    panel = await CatalogService(session).client_for_panel(service.panel_id)
    await VpnServiceManager(session, panel).reenable(service)
    await send_supergroup_message(
        session,
        callback.bot,
        "orders",
        f"سرویس دوباره فعال شد\nکاربر: {user.telegram_id}\nاکانت: {service.pasarguard_username}",
    )
    await callback.message.answer("سرویس دوباره فعال شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("svc_delete:"))
async def delete_service(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(callback.from_user)
    service = await session.get(VpnService, int(callback.data.split(":", 1)[1]))
    if not service or service.user_id != user.id:
        await callback.answer("سرویس پیدا نشد.", show_alert=True)
        return
    panel = await CatalogService(session).client_for_panel(service.panel_id)
    await VpnServiceManager(session, panel).delete(service)
    await send_supergroup_message(
        session,
        callback.bot,
        "account_changes",
        f"کاربر سرویس را حذف کرد\nکاربر: {user.telegram_id}\nاکانت: {service.pasarguard_username}",
    )
    await callback.message.answer("سرویس حذف شد.")
    await callback.answer()


async def wallet(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    await message.answer(f"موجودی کیف پول: {user.wallet_balance_toman:,} تومان")


async def invite(message: Message, session: AsyncSession) -> None:
    await UserService(session).get_or_create(message.from_user)
    bot = await message.bot.get_me()
    await message.answer(f"لینک دعوت شما:\nhttps://t.me/{bot.username}?start=ref_{message.from_user.id}")


async def charge_wallet(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    if user.is_blocked:
        await message.answer("حساب شما مسدود شده است.")
        return
    await state.set_state(ChargeWallet.amount)
    await message.answer("مبلغ شارژ را به تومان وارد کنید:")


@router.message(ChargeWallet.amount)
async def charge_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = int((message.text or "").replace(",", "").strip())
    except ValueError:
        await message.answer("لطفاً فقط عدد وارد کنید.")
        return
    if amount <= 0:
        await message.answer("مبلغ باید بیشتر از صفر باشد.")
        return
    await state.update_data(amount=amount)
    settings = SettingsService(session)
    enabled = set()
    for method in PaymentMethod:
        if await settings.get_bool(f"payment_{method.value}_enabled", method == PaymentMethod.card):
            enabled.add(method.value)
    await message.answer("روش پرداخت را انتخاب کنید:", reply_markup=payment_methods(enabled))


@router.callback_query(F.data.startswith("pay:"))
async def payment_method_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(callback.from_user)
    amount = int((await state.get_data()).get("amount", 0))
    method = PaymentMethod(callback.data.split(":", 1)[1])
    settings = SettingsService(session)
    payments = PaymentService(session)
    if method == PaymentMethod.card:
        payment = await payments.create_card_request(user, amount)
        card = await settings.get("card_number", "")
        holder = await settings.get("card_holder", "")
        await callback.message.answer(
            f"مبلغ {amount:,} تومان را به کارت زیر واریز کنید:\nشماره کارت: {card}\nنام صاحب کارت: {holder}",
            reply_markup=receipt_button(payment.id),
        )
    elif method == PaymentMethod.stars:
        rate = await settings.get_int("stars_to_toman_rate", 1000)
        prices = [LabeledPrice(label="شارژ کیف پول", amount=max(1, amount // rate))]
        await callback.message.answer_invoice(
            title="شارژ کیف پول",
            description=f"شارژ کیف پول به مبلغ {amount:,} تومان",
            payload=f"stars:{amount}",
            currency="XTR",
            prices=prices,
        )
    else:
        payment = await payments.create_crypto_request(user, amount, method)
        await callback.message.answer(f"لینک پرداخت:\n{payment.provider_url}")
    await callback.answer()


@router.callback_query(F.data.startswith("receipt:"))
async def ask_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(payment_id=int(callback.data.split(":", 1)[1]))
    await state.set_state(ChargeWallet.receipt)
    await callback.message.answer("لطفاً تصویر رسید پرداخت را ارسال کنید.")
    await callback.answer()


@router.message(ChargeWallet.receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext, session: AsyncSession) -> None:
    payment = await session.get(PaymentRequest, (await state.get_data())["payment_id"])
    if not payment:
        await message.answer("درخواست پرداخت پیدا نشد.")
        return
    payment.receipt_file_id = message.photo[-1].file_id
    payment.status = PaymentStatus.pending.value
    from app.bot.keyboards.admin import receipt_review

    caption = f"رسید #{payment.id}\nکاربر: {message.from_user.id}\nمبلغ: {payment.amount_toman:,} تومان"
    sent_to_group = await send_supergroup_photo(
        session,
        message.bot,
        "receipts",
        payment.receipt_file_id,
        caption,
        reply_markup=receipt_review(payment.id),
    )
    if not sent_to_group:
        admins = await SettingsService(session).admin_ids()
        for admin_id in admins:
            await message.bot.send_photo(
                admin_id,
                payment.receipt_file_id,
                caption=caption,
                reply_markup=receipt_review(payment.id),
            )
    await state.clear()
    await message.answer("رسید شما برای بررسی ادمین ارسال شد.")


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def stars_paid(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_or_create(message.from_user)
    amount = int(message.successful_payment.invoice_payload.split(":", 1)[1])
    await WalletService(session).add(user, amount, TransactionKind.deposit, "شارژ کیف پول با استارز تلگرام")
    await message.answer(f"کیف پول شما به مبلغ {amount:,} تومان شارژ شد.")


async def support(message: Message) -> None:
    await message.answer(f"پشتیبانی: @{env_settings.support_username}")


@router.message(F.text)
async def user_menu_dispatch(message: Message, state: FSMContext, session: AsyncSession) -> None:
    action = await MenuService(session).action_for_text(message.text or "")
    if action == "buy_service":
        await buy_service(message, session)
    elif action == "my_services":
        await my_services(message, session)
    elif action == "wallet":
        await wallet(message, session)
    elif action == "invite":
        await invite(message, session)
    elif action == "charge_wallet":
        await charge_wallet(message, state, session)
    elif action == "test_account":
        await test_account(message, session)
    elif action == "support":
        await support(message)
