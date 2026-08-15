"""Bot Telegram: laporan trading terjadwal (harian/mingguan/bulanan, 08:00 WIB) + alert
instan kill-switch drawdown + command manual override daily/monthly (bukan total, itu tetap
permanen). Polling (bukan webhook) -- cocok utk laptop lokal tanpa domain publik.

Lifecycle python-telegram-bot di-embed manual (initialize/start/updater.start_polling), BUKAN
run_polling() yang blocking -- supaya bisa jalan bareng event loop uvicorn/FastAPI yang sudah
ada, dipanggil dari lifespan main.py (setelah trading polling start, spy trading gak pernah
gagal start gara-gara Telegram bermasalah)."""

from typing import cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import BotCommand, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.core.config import settings
from app.core.logging import logger
from app.features.bot_telegram.schema import ReportPeriod
from app.features.bot_telegram.usecase import (
    _generate_and_send_report,
    check_and_alert_drawdown,
    handle_callback_query,
    handle_start_tuning_command,
    is_authorized_user,
)

DRAWDOWN_CHECK_INTERVAL_SECONDS = 30

_BOT_COMMANDS = [
    BotCommand("report_harian", "Laporan trading hari kemarin"),
    BotCommand("report_mingguan", "Laporan trading 7 hari terakhir"),
    BotCommand("report_bulanan", "Laporan trading bulan kemarin"),
    BotCommand("start_tuning_harian", "Evaluasi & override kill-switch harian"),
    BotCommand("start_tuning_bulanan", "Evaluasi & override kill-switch bulanan"),
]

_application: Application | None = None
_scheduler: AsyncIOScheduler | None = None


async def _cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE, period: ReportPeriod) -> None:
    await _generate_and_send_report(period)


async def _cmd_report_harian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_report(update, context, "daily")


async def _cmd_report_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_report(update, context, "weekly")


async def _cmd_report_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_report(update, context, "monthly")


async def _cmd_start_tuning(
    update: Update, context: ContextTypes.DEFAULT_TYPE, period: ReportPeriod
) -> None:
    user = update.effective_user
    if user is None or not is_authorized_user(user.id):
        if update.message:
            await update.message.reply_text("Tidak diizinkan.")
        return
    await handle_start_tuning_command(period)


async def _cmd_start_tuning_harian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_start_tuning(update, context, "daily")


async def _cmd_start_tuning_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _cmd_start_tuning(update, context, "monthly")


async def _on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    user = query.from_user
    if user is None or not is_authorized_user(user.id):
        await query.answer("Tidak diizinkan.")
        return

    try:
        action, period_str = query.data.split(":", 1)
    except ValueError:
        await query.answer()
        return

    if period_str not in ("daily", "weekly", "monthly"):
        await query.answer()
        return
    period = cast(ReportPeriod, period_str)

    reply_text = await handle_callback_query(period, action)
    await query.answer()
    message = query.message
    if message is not None and isinstance(message, Message):
        await message.reply_text(reply_text)


async def _job_report(period: ReportPeriod) -> None:
    await _generate_and_send_report(period)


async def _job_drawdown_check() -> None:
    await check_and_alert_drawdown()


async def start_bot() -> None:
    global _application, _scheduler

    if not settings.telegram_token_xauusd or not settings.telegram_chat_id:
        logger.warning("[bot_telegram] TELEGRAM_TOKEN_XAUUSD/TELEGRAM_CHAT_ID kosong, bot tidak dijalankan")
        return

    _application = Application.builder().token(settings.telegram_token_xauusd).build()
    _application.add_handler(CommandHandler("report_harian", _cmd_report_harian))
    _application.add_handler(CommandHandler("report_mingguan", _cmd_report_mingguan))
    _application.add_handler(CommandHandler("report_bulanan", _cmd_report_bulanan))
    _application.add_handler(CommandHandler("start_tuning_harian", _cmd_start_tuning_harian))
    _application.add_handler(CommandHandler("start_tuning_bulanan", _cmd_start_tuning_bulanan))
    _application.add_handler(CallbackQueryHandler(_on_callback_query))

    await _application.initialize()
    await _application.bot.set_my_commands(_BOT_COMMANDS)
    await _application.start()
    if _application.updater is not None:
        await _application.updater.start_polling()

    _scheduler = AsyncIOScheduler()

    if settings.telegram_reports_enabled:
        _scheduler.add_job(
            _job_report,
            CronTrigger(hour=settings.telegram_daily_report_hour_utc, minute=0),
            args=["daily"],
            id="bot_telegram_daily_report",
        )
        _scheduler.add_job(
            _job_report,
            CronTrigger(
                day_of_week=settings.telegram_weekly_report_weekday,
                hour=settings.telegram_weekly_report_hour_utc,
                minute=0,
            ),
            args=["weekly"],
            id="bot_telegram_weekly_report",
        )
        _scheduler.add_job(
            _job_report,
            CronTrigger(day=1, hour=settings.telegram_monthly_report_hour_utc, minute=0),
            args=["monthly"],
            id="bot_telegram_monthly_report",
        )

    _scheduler.add_job(
        _job_drawdown_check,
        "interval",
        seconds=DRAWDOWN_CHECK_INTERVAL_SECONDS,
        id="bot_telegram_drawdown_check",
    )
    _scheduler.start()

    logger.info("[bot_telegram] Bot Telegram start (polling)")


async def stop_bot() -> None:
    global _application, _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

    if _application is not None:
        if _application.updater is not None:
            await _application.updater.stop()
        await _application.stop()
        await _application.shutdown()
        _application = None
        logger.info("[bot_telegram] Bot Telegram stop")
