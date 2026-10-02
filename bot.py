import asyncio
from datetime import datetime, timezone, timedelta
import json
import os
import re
import sqlite3
import aiohttp
import pandas as pd
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    LabeledPrice,
    PreCheckoutQuery,
)
from google import genai
from google.genai import types

# ==================== НАСТРОЙКА КЛЮЧЕЙ И ПРОМПТА ====================
TELEGRAM_TOKEN = "6035634793:AAEZtNPmvuJar35GyRP4jOrbcUG123RyFC4"
PUBLIC_CHANNEL_ID = -1004451722414  # Обычный канал (если нужен для других отчетов)
PREMIUM_CHANNEL_ID = -1004453114256 # Премиум-канал (где публикуются сигналы и обновляются статусы)
PROVIDER_TOKEN = ""  # Пусто для Telegram Stars (XTR)
CHECK_INTERVAL = 3600 # 1 час (в секундах)

# Путь к базе данных (сохраняется на постоянный диск /data)
DB_PATH = os.getenv("DB_PATH", "/data/bot_users.db")

# БЕЗОПАСНОЕ ЧТЕНИЕ КЛЮЧЕЙ ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (НЕ ВЫЗЫВАЕТ БЛОКИРОВКУ GITHUB)
GEMINI_KEYS = [
    os.getenv("GCP_API_KEY", "your_api_key_1"),
    os.getenv("GEMINI_KEY_2", "your_api_key_2"),
    os.getenv("GEMINI_KEY_3", "your_api_key_3"),
]

current_key_index = 0

SYSTEM_PROMPT = """
Ты — профессиональный алго-трейдер и аналитик криптовалютного рынка, использующий концепции Smart Money (SMC) и Price Action. Твоя задача — проанализировать предоставленные рыночные данные и выдать детальный торговый план в формате JSON.

ПРАВИЛО РАССТАНОВКИ СТОП-ЛОССА (CRITICAL SMART MONEY RULE):
Стоп-лосс ВСЕГДА должен размещаться строго за защищенным структурным минимумом (для LONG) или максимумом (для SHORT), а также за нижней/верхней границей паттерна Order Block (OB). Категорически запрещено «подтягивать» или уменьшать стоп-лосс ради красивого процента риска, если за уровнем ордер-блока или локальной ликвидностью остается незащищенная зона. Стоп должен быть технически обоснован сломом структуры (BOS/CHoCH).
"""


def get_current_ai_client():
  global current_key_index
  return genai.Client(api_key=GEMINI_KEYS[current_key_index])


ai_client = get_current_ai_client()
# ==========================================================

LOGO_PHOTO_URL = "https://i.ibb.co/6y1W6h9/iqtrend-logo.png"

bot = Bot(
    token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ==================== МУЛЬТИЯЗЫЧНЫЕ КНОПКИ ====================
BUTTONS = {
    "uk": {
        "signal": "🔍 Отримати сигнал",
        "how": "❓ Як це працює?",
        "payment": "💳 Оплата",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Знайти інший актив",
        "back_main": "🏠 Головне меню",
        "back": "← Назад",
        "short": "⚡ Короткостроковий",
        "mid": "📈 Середньостроковий",
        "recalc": "🔄 Перерахувати",
        "other": "🔍 Інший актив",
        "new_analysis": "🔍 Новий аналіз",
    },
    "es": {
        "signal": "🔍 Obtener señal",
        "how": "❓ ¿Cómo funciona?",
        "payment": "💳 Pago",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Buscar otro activo",
        "back_main": "🏠 Menú principal",
        "back": "← Volver",
        "short": "⚡ Corto plazo",
        "mid": "📈 Medio plazo",
        "recalc": "🔄 Recalcular",
        "other": "🔍 Otro activo",
        "new_analysis": "🔍 Nuevo análisis",
    },
    "pt": {
        "signal": "🔍 Obter sinal",
        "how": "❓ Como funciona?",
        "payment": "💳 Pagamento",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Encontrar outro ativo",
        "back_main": "🏠 Menu principal",
        "back": "← Voltar",
        "short": "⚡ Curto prazo",
        "mid": "📈 Médio prazo",
        "recalc": "🔄 Recalcular",
        "other": "🔍 Outro ativo",
        "new_analysis": "🔍 Nova análise",
    },
    "fr": {
        "signal": "🔍 Obtenir un signal",
        "how": "❓ Comment ça marche ?",
        "payment": "💳 Paiement",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Trouver un autre actif",
        "back_main": "🏠 Menu principal",
        "back": "← Retour",
        "short": "⚡ Court terme",
        "mid": "📈 Moyen terme",
        "recalc": "🔄 Recalculer",
        "other": "🔍 Autre actif",
        "new_analysis": "🔍 Nouvelle analyse",
    },
    "de": {
        "signal": "🔍 Signal erhalten",
        "how": "❓ Wie es funktioniert?",
        "payment": "💳 Zahlung",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Anderes Asset finden",
        "back_main": "🏠 Hauptmenü",
        "back": "← Zurück",
        "short": "⚡ Kurzfristig",
        "mid": "📈 Mittelfristig",
        "recalc": "🔄 Neu berechnen",
        "other": "🔍 Anderes Asset",
        "new_analysis": "🔍 Neue Analyse",
    },
    "it": {
        "signal": "🔍 Ottieni segnale",
        "how": "❓ Come funziona?",
        "payment": "💳 Pagamento",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Trova un altro asset",
        "back_main": "🏠 Menu principale",
        "back": "← Indietro",
        "short": "⚡ Breve termine",
        "mid": "📈 Medio termine",
        "recalc": "🔄 Ricalcola",
        "other": "🔍 Altro asset",
        "new_analysis": "🔍 Nuova analisi",
    },
    "en": {
        "signal": "🔍 Get Signal",
        "how": "❓ How it works?",
        "payment": "💳 Payment",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Find another asset",
        "back_main": "🏠 Main Menu",
        "back": "← Back",
        "short": "⚡ Short-term",
        "mid": "📈 Mid-term",
        "recalc": "🔄 Recalculate",
        "other": "🔍 Other asset",
        "new_analysis": "🔍 New Analysis",
    },
    "ru": {
        "signal": "🔍 Получить сигнал",
        "how": "❓ Как это работает?",
        "payment": "💳 Оплата",
        "btc": "₿ BTC",
        "eth": "Ξ ETH",
        "other_asset": "🔍 Найти другой актив",
        "back_main": "🏠 Главное меню",
        "back": "← Назад",
        "short": "⚡ Краткосрочный",
        "mid": "📈 Среднесрочный",
        "recalc": "🔄 Пересчитать",
        "other": "🔍 Другой актив",
        "new_analysis": "🔍 Новый анализ",
    },
}


def get_btn_text(key: str, user_language_code: str) -> str:
  lang = "en"
  if user_language_code:
    lang_prefix = user_language_code[:2].lower()
    if lang_prefix in BUTTONS:
      lang = lang_prefix
  return BUTTONS[lang].get(key, BUTTONS["en"].get(key, key))


def extract_json_from_text(text: str) -> str:
  match = re.search(r"\{.*\}", text, re.DOTALL)
  if match:
    return match.group(0)
  return text


# ==================== ФОРМАТИРОВАНИЕ СИГНАЛА ====================
def format_signal_message(ai_response_data, status_text=""):
  direction_emoji = (
      "🟢 LONG" if ai_response_data.get("direction") == "LONG" else "🔴 SHORT"
  )

  logic_entry = ai_response_data.get("entry_logic", "")
  logic_targets = ai_response_data.get("targets_logic", "")
  logic_inv = ai_response_data.get("invalidation_logic", "")

  tp1_pct = ai_response_data.get("tp1_percent", "60")
  tp2_pct = ai_response_data.get("tp2_percent", "40")

  status_block = f"\n\n{status_text}" if status_text else ""

  message = (
      f"{direction_emoji} • {ai_response_data.get('symbol')}\n"
      f"⚡️ FUTURES - LIMIT\n"
      f"⭐ Качество сценария — {ai_response_data.get('quality_percent')}%\n"
      f"⚠ Качество ниже среднего — сценарий можно пропустить или взять"
      f" меньшим объёмом.\n\n"
      f"🤖 ВХОД — ${ai_response_data.get('entry_price')}\n"
      f"Зона: {ai_response_data.get('entry_zone')}\n\n"
      f"🔴 STOP LOSS — ${ai_response_data.get('stop_loss')} -"
      f" {ai_response_data.get('stop_loss_percent')}% от входа\n\n"
      f"🎯 ЦЕЛИ\n"
      f"1️⃣ ${ai_response_data.get('tp1_price')} -"
      f" {ai_response_data.get('tp1_r')}R - закрыть {tp1_pct}%\n"
      f"2️⃣ ${ai_response_data.get('tp2_price')} -"
      f" {ai_response_data.get('tp2_r')}R - закрыть {tp2_pct}%\n\n"
      f"📍 <blockquote expandable><b>ЛОГИКА ВХОДА</b>\n{logic_entry}</blockquote>\n\n"
      f"🎯 <blockquote expandable><b>ЛОГИКА ЦЕЛЕЙ</b>\n{logic_targets}</blockquote>\n\n"
      f"🚫 <blockquote"
      f" expandable><b>КОГДА ПЛАН ОТМЕНЯЕТСЯ?</b>\n{logic_inv}</blockquote>"
      f"{status_block}\n\n"
      f"_Не инвестиционная рекомендация. Расчёт по структуре графика и SMC._"
  )
  return message


# ==================== АВТОПЕРЕВОД ЧЕРЕЗ ИИ ====================
async def translate_text_for_user(text: str, user_language_code: str) -> str:
  if not user_language_code or user_language_code.startswith("ru"):
    return text
  lang_code = user_language_code[:2].lower()
  try:
    prompt = (
        f"Translate the following text to the language with ISO code"
        f" '{lang_code}'. Keep all HTML tags (like <b>, <i>, <code>, <blockquote"
        " expandable>) exactly as they are. Do not add any extra comments, just"
        f" output the translated text:\n\n{text}"
    )
    response = ai_client.models.generate_content(
        model="gemini-3.8-flash", contents=prompt
    )
    if response and response.text:
      return response.text.strip()
  except Exception as e:
    print(f"Ошибка перевода: {e}")
  return text


async def get_binance_price(symbol: str) -> float:
  url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
  try:
    async with aiohttp.ClientSession() as session:
      async with session.get(url, timeout=5) as response:
        if response.status == 200:
          data = await response.json()
          return float(data.get("price", 0))
  except Exception as e:
    print(f"Ошибка получения цены Binance для {symbol}: {e}")
  return 0.0


# ==================== РАСЧЕТ ИНДИКАТОРОВ ====================
async def calculate_market_indicators(symbol: str, interval: str = "1h") -> dict:
  url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500"
  try:
    async with aiohttp.ClientSession() as session:
      async with session.get(url, timeout=5) as response:
        if response.status == 200:
          data = await response.json()
          df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "close_time", "qav", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"])
          df["close"] = df["close"].astype(float)
          close = df["close"]
          ema_200 = close.ewm(span=200, adjust=False).mean()
          ema_slope = (ema_200.iloc[-1] - ema_200.iloc[-5]) / ema_200.iloc[-5]
          is_rising = ema_slope > 0.0001
          is_falling = ema_slope < -0.0001
          delta = close.diff()
          gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
          loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
          rs = gain / loss
          rsi = 100 - (100 / (1 + rs))
          last_close = close.iloc[-1]
          last_ema = ema_200.iloc[-1]
          last_rsi = rsi.iloc[-1]
          if last_close > last_ema and is_rising:
            trend = "BULLISH (Strong - Price above rising EMA 200)"
          elif last_close < last_ema and is_falling:
            trend = "BEARISH (Strong - Price below falling EMA 200)"
          else:
            trend = "FLAT / CHOPPY (EMA 200 is flat or price is crossing it)"
          return {
              "success": True,
              "trend": trend,
              "rsi": round(last_rsi, 2),
              "price": last_close,
              "is_rising": is_rising,
              "is_falling": is_falling,
          }
  except Exception as e:
    print(f"Ошибка расчета индикаторов: {e}")
  return {"success": False}


# ==================== БАЗА ДАННЫХ И МИГРАЦИИ ====================
def init_db():
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                requests_left INTEGER DEFAULT 180,
                daily_used INTEGER DEFAULT 0,
                last_reset_date TEXT,
                sub_expires_at TEXT,
                referrer_id INTEGER,
                first_request_made INTEGER DEFAULT 0,
                lang TEXT,
                total_requests INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_signals (
                signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                tf_type TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp1_price REAL,
                tp2_price REAL,
                channel_message_id INTEGER,
                status TEXT DEFAULT 'PENDING',
                is_triggered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    try:
      cursor.execute("ALTER TABLE active_signals ADD COLUMN user_id INTEGER;")
    except Exception:
      pass

    try:
      cursor.execute("ALTER TABLE active_signals ADD COLUMN is_triggered INTEGER DEFAULT 0;")
    except Exception:
      pass

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_tp INTEGER DEFAULT 0,
                total_sl INTEGER DEFAULT 0
            )
        """)
    cursor.execute("""
            INSERT OR IGNORE INTO channel_stats (id, total_tp, total_sl) 
            VALUES (1, 0, 0)
        """)
    conn.commit()


def update_and_get_stats(result_type: str):
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    if result_type == "TP":
      cursor.execute("UPDATE channel_stats SET total_tp = total_tp + 1 WHERE id = 1")
    elif result_type == "SL":
      cursor.execute("UPDATE channel_stats SET total_sl = total_sl + 1 WHERE id = 1")
    conn.commit()
    
    cursor.execute("SELECT total_tp, total_sl FROM channel_stats WHERE id = 1")
    row = cursor.fetchone()
    return row if row else (0, 0)


def get_active_signal(symbol: str, tf_type: str, user_id: int = None):
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    if user_id is not None:
      cursor.execute(
          """
              SELECT direction, entry_price, stop_loss, tp1_price, tp2_price, created_at 
              FROM active_signals 
              WHERE symbol = ? AND tf_type = ? AND user_id = ? AND status = 'PENDING' 
              ORDER BY created_at DESC LIMIT 1
          """,
          (symbol, tf_type, user_id),
      )
    else:
      cursor.execute(
          """
              SELECT direction, entry_price, stop_loss, tp1_price, tp2_price, created_at 
              FROM active_signals 
              WHERE symbol = ? AND tf_type = ? AND user_id IS NULL AND status = 'PENDING' 
              ORDER BY created_at DESC LIMIT 1
          """,
          (symbol, tf_type),
      )
    return cursor.fetchone()


def save_active_signal(
    symbol: str,
    tf_type: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    tp1_price: float,
    tp2_price: float,
    channel_message_id: int = None,
    user_id: int = None,
):
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO active_signals 
            (user_id, symbol, tf_type, direction, entry_price, stop_loss, tp1_price, tp2_price, channel_message_id, status, is_triggered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0)
        """,
        (
            user_id,
            symbol,
            tf_type,
            direction,
            entry_price,
            stop_loss,
            tp1_price,
            tp2_price,
            channel_message_id,
        ),
    )
    conn.commit()


def register_user(user_id: int, username: str, full_name: str, lang: str = "ru", referrer_id: int = None):
  today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
      ref_to_save = referrer_id if (referrer_id and referrer_id != user_id) else None
      cursor.execute(
          "INSERT INTO users (user_id, username, full_name, requests_left, daily_used, last_reset_date, referrer_id, first_request_made, lang, total_requests) VALUES (?, ?, ?, 180, 0, ?, ?, 0, ?, 0)",
          (user_id, username or "", full_name or "", today_str, ref_to_save, lang),
      )
      conn.commit()


def get_user_status(user_id: int):
  today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT requests_left, daily_used, last_reset_date, sub_expires_at, total_requests FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
      return 0, 0, False, 0
    requests_left, daily_used, last_reset_date, sub_expires_at, total_requests = row
    is_sub_active = False
    if sub_expires_at:
      try:
        if datetime.fromisoformat(sub_expires_at) > datetime.now(timezone.utc):
          is_sub_active = True
      except Exception:
        pass
    if last_reset_date != today_str and not is_sub_active:
      daily_used = 0
      cursor.execute(
          "UPDATE users SET daily_used = 0, last_reset_date = ? WHERE user_id = ?",
          (today_str, user_id),
      )
      conn.commit()
  return requests_left, daily_used, is_sub_active, total_requests


def use_request_and_check_referral(user_id: int, bot: Bot):
  today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT referrer_id, first_request_made FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    referrer_id = row[0] if row else None
    first_request_made = row[1] if row else 0
    cursor.execute(
        "UPDATE users SET requests_left = requests_left - 1, daily_used = daily_used + 1, total_requests = total_requests + 1, last_reset_date = ? WHERE user_id = ?",
        (today_str, user_id),
    )
    is_first_ever = False
    if first_request_made == 0 and referrer_id:
      cursor.execute(
          "UPDATE users SET first_request_made = 1 WHERE user_id = ?", (user_id,)
      )
      cursor.execute(
          "UPDATE users SET daily_used = 0 WHERE user_id = ?", (referrer_id,)
      )
      is_first_ever = True
    conn.commit()
    if is_first_ever and referrer_id:
      asyncio.create_task(notify_referrer(bot, referrer_id))


async def notify_referrer(bot: Bot, referrer_id: int):
  try:
    ref_msg = (
        "🎉 <b>Ваш приглашенный друг сделал свой первый запрос!</b>\n\nВаш"
        " дневной лимит запросов полностью обнулен — вам снова доступно"
        " <b>6 из 6 запросов</b> на сегодня! 🚀"
    )
    await bot.send_message(
        chat_id=referrer_id, text=ref_msg, parse_mode=ParseMode.HTML
    )
  except Exception:
    pass


def activate_subscription(user_id: int, days: int = 0, hours: int = 0):
  with sqlite3.connect(DB_PATH, timeout=20) as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sub_expires_at FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    current_expire = None
    if row and row[0]:
      try:
        current_expire = datetime.fromisoformat(row[0])
      except Exception:
        pass
    now_utc = datetime.now(timezone.utc)
    start_base = current_expire if (current_expire and current_expire > now_utc) else now_utc
    new_expire = start_base + timedelta(days=days, hours=hours)
    cursor.execute(
        "UPDATE users SET sub_expires_at = ? WHERE user_id = ?",
        (new_expire.isoformat(), user_id),
    )
    conn.commit()


# ==================== ГЕНЕРАЦИЯ С ИИ (С УСТОЙЧИВОСТЬЮ К ОШИБКАМ) ====================
async def generate_with_retry(prompt: str, max_retries: int = 15):
  global current_key_index, ai_client
  for attempt in range(max_retries):
    try:
      response = ai_client.models.generate_content(
          model="gemini-3.8-flash",
          contents=prompt,
      )
      if response and response.text:
        return response.text
    except Exception as e:
      err_str = str(e)
      print(f"⚠️ Ошибка с ключом #{current_key_index + 1}: {err_str}. Переключаю ключ...")
      
      current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
      ai_client = get_current_ai_client()
      
      await asyncio.sleep(5)
      
      if attempt == max_retries - 1:
        raise e
        
  raise Exception("Не удалось получить ответ от Gemini API со всех ключей.")


# ==================== АВТОМАТИЧЕСКИЙ СКАНЕР РЫНКА (КАЖДЫЙ ЧАС) ====================
async def auto_scanner_worker(bot: Bot):
  print("Запущен автоматический сканер рынка с интервалом 1 час...")
  while True:
    try:
      print(f"[{datetime.now(timezone.utc)}] Запуск планового сканирования рынка...")
      
      url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
      async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
          if response.status == 200:
            data = await response.json()
            usdt_pairs = [
                item for item in data 
                if item["symbol"].endswith("USDT") and not any(x in item["symbol"] for x in ["DOWN", "UP", "BULL", "BEAR"])
            ]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
            top_20 = sorted_pairs[:20]
            top_symbols = [item["symbol"] for item in top_20]
          else:
            top_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

      scored_candidates = []
      for symbol in top_symbols[:5]:
        indicators = await calculate_market_indicators(symbol, interval="4h")
        if not indicators["success"]:
          continue
        
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Analyze crypto futures for {symbol} on 4h timeframe using Smart Money Concepts (SMC).\n"
            f"Current price: ${indicators['price']}, Trend: {indicators['trend']}, RSI: {indicators['rsi']}.\n"
            "Evaluate the quality of the SMC setup (Order Blocks, FVG, Market Structure/BOS/CHoCH).\n"
            "Return ONLY a valid JSON object, no markdown, with keys:\n"
            "{\n"
            f'  "symbol": "{symbol}",\n'
            '  "direction": "LONG" or "SHORT",\n'
            '  "quality_percent": [число от 0 до 100],\n'
            '  "entry_price": "[цена]",\n'
            '  "entry_zone": "[зона]",\n'
            '  "stop_loss": "[стоп]",\n'
            '  "stop_loss_percent": "[процент]",\n'
            '  "tp1_price": "[tp1]",\n'
            '  "tp1_r": "[r1]",\n'
            '  "tp1_percent": "60",\n'
            '  "tp2_price": "[tp2]",\n'
            '  "tp2_r": "[r2]",\n'
            '  "tp2_percent": "40",\n'
            '  "entry_logic": "[логика входа]",\n'
            '  "targets_logic": "[логика целей]",\n'
            '  "invalidation_logic": "[отмена плана]"\n'
            "}"
        )
        try:
          raw = await generate_with_retry(prompt)
          clean_json_str = extract_json_from_text(raw)
          parsed = json.loads(clean_json_str)
          qual = float(parsed.get("quality_percent", 0))
          scored_candidates.append((qual, parsed))
        except Exception as json_err:
          print(f"❌ Ошибка получения/парсинга JSON для {symbol}: {json_err}")
          
        await asyncio.sleep(4)

      scored_candidates.sort(key=lambda x: x[0], reverse=True)
      best_two = [item[1] for item in scored_candidates[:2]]

      for ai_response_data in best_two:
        symbol = ai_response_data.get("symbol")
        tf_type = "mid"
        
        if get_active_signal(symbol, tf_type, user_id=None):
          continue

        message_text = format_signal_message(ai_response_data, status_text="🤖 <b>Автоматический сканер SMC (Топ-2 рынка)</b>")

        sent_msg = await bot.send_message(
            chat_id=PREMIUM_CHANNEL_ID,
            text=message_text,
            parse_mode=ParseMode.HTML
        )

        save_active_signal(
            symbol=symbol,
            tf_type=tf_type,
            direction=ai_response_data.get("direction"),
            entry_price=float(ai_response_data.get("entry_price", 0)),
            stop_loss=float(ai_response_data.get("stop_loss", 0)),
            tp1_price=float(ai_response_data.get("tp1_price", 0)),
            tp2_price=float(ai_response_data.get("tp2_price", 0)),
            channel_message_id=sent_msg.message_id,
            user_id=None,
        )
        await asyncio.sleep(3)

    except Exception as e:
      print(f"❌ Критическая ошибка в авто-сканере рынка: {repr(e)}")

    await asyncio.sleep(CHECK_INTERVAL)


# ==================== ФОНОВЫЙ МОНИТОРИНГ ЦЕН С УЧЕТОМ АКТИВАЦИИ ЛИМИТКИ ====================
async def check_active_signals_worker(bot: Bot):
  print("Запущен фоновый мониторинг отработки сигналов...")
  while True:
    await asyncio.sleep(120)
    try:
      with sqlite3.connect(DB_PATH, timeout=20) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT signal_id, user_id, symbol, direction, entry_price, stop_loss, tp1_price, tp2_price, channel_message_id, is_triggered, created_at 
                FROM active_signals 
                WHERE status = 'PENDING'
            """
        )
        pending_signals = cursor.fetchall()

      if not pending_signals:
        continue

      for sig in pending_signals:
        signal_id, user_id, symbol, direction, entry_price, stop_loss, tp1_price, tp2_price, channel_message_id, is_triggered, created_at = sig
        
        current_price = await get_binance_price(symbol)
        if current_price == 0.0:
          continue

        try:
          created_dt = datetime.fromisoformat(created_at)
          if datetime.now(timezone.utc) - created_dt > timedelta(hours=24) and is_triggered == 0:
            with sqlite3.connect(DB_PATH, timeout=20) as conn:
              cursor = conn.cursor()
              cursor.execute("UPDATE active_signals SET status = 'EXPIRED' WHERE signal_id = ?", (signal_id,))
              conn.commit()
            continue
        except Exception:
          pass

        new_status_text = None
        result_type = None
        new_is_triggered = is_triggered

        if direction == "LONG":
          if is_triggered == 0:
            if current_price >= tp1_price:
              new_status_text = "⚪️ <b>СТАТУС: СИГНАЛ ОТМЕНЕН (Цена ушла без касания входа) ❌</b>"
              result_type = "EXPIRED"
            elif current_price <= stop_loss:
              new_status_text = "🔴 <b>СТАТУС: СТОП ДО АКТИВАЦИИ СРАБОТАЛ ❌</b>"
              result_type = "SL"
            elif current_price <= entry_price + (entry_price * 0.001):
              new_is_triggered = 1
          
          if new_is_triggered == 1 and not result_type:
            if current_price <= stop_loss:
              new_status_text = "🔴 <b>СТАТУС: СТОП-ЛОСС СРАБОТАЛ ❌</b>"
              result_type = "SL"
            elif current_price >= tp2_price:
              new_status_text = "🎯 <b>СТАТУС: ЦЕЛЬ 2 ДОСТИГНУТА (+TP2) ✅</b>"
              result_type = "TP"
            elif current_price >= tp1_price:
              new_status_text = "🎯 <b>СТАТУС: ЦЕЛЬ 1 ДОСТИГНУТА (+TP1) ✅</b>"
              result_type = "TP"

        elif direction == "SHORT":
          if is_triggered == 0:
            if current_price <= tp1_price:
              new_status_text = "⚪️ <b>СТАТУС: СИГНАЛ ОТМЕНЕН (Цена ушла без касания входа) ❌</b>"
              result_type = "EXPIRED"
            elif current_price >= stop_loss:
              new_status_text = "🔴 <b>СТАТУС: СТОП ДО АКТИВАЦИИ СРАБОТАЛ ❌</b>"
              result_type = "SL"
            elif current_price >= entry_price - (entry_price * 0.001):
              new_is_triggered = 1

          if new_is_triggered == 1 and not result_type:
            if current_price >= stop_loss:
              new_status_text = "🔴 <b>СТАТУС: СТОП-ЛОСС СРАБОТАЛ ❌</b>"
              result_type = "SL"
            elif current_price <= tp2_price:
              new_status_text = "🎯 <b>СТАТУС: ЦЕЛЬ 2 ДОСТИГНУТА (+TP2) ✅</b>"
              result_type = "TP"
            elif current_price <= tp1_price:
              new_status_text = "🎯 <b>СТАТУС: ЦЕЛЬ 1 ДОСТИГНУТА (+TP1) ✅</b>"
              result_type = "TP"

        if new_is_triggered != is_triggered and not result_type:
          with sqlite3.connect(DB_PATH, timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE active_signals SET is_triggered = 1 WHERE signal_id = ?", (signal_id,))
            conn.commit()

        if new_status_text and result_type:
          if result_type in ["TP", "SL"]:
            total_tp, total_sl = update_and_get_stats(result_type)
            stats_block = (
                f"📊 <b>УЧЁТ СИГНАЛОВ КАНАЛА:</b>\n"
                f"🟢 Take Profit: <b>+{total_tp}</b> | 🔴 Stop Loss: <b>+{total_sl}</b>"
            )
          else:
            stats_block = "ℹ️ <i>Сценарий аннулирован до активации лимитного ордера (ушел без отката).</i>"

          try:
            direction_emoji = "🟢 LONG" if direction == "LONG" else "🔴 SHORT"
            updated_channel_text = (
                f"{direction_emoji} • {symbol}\n"
                f"⚡ FUTURES - LIMIT\n\n"
                f"🤖 ВХОД — ${entry_price}\n"
                f"🔴 STOP LOSS — ${stop_loss}\n"
                f"🎯 ЦЕЛЬ 1 — ${tp1_price}\n"
                f"🎯 ЦЕЛЬ 2 — ${tp2_price}\n\n"
                f"{new_status_text}\n\n"
                f"-----------------------------------\n"
                f"{stats_block}\n\n"
                f"_Не инвестиционная рекомендация. Расчёт по структуре графика и SMC._"
            )
            
            if channel_message_id:
              await bot.edit_message_text(
                  chat_id=PREMIUM_CHANNEL_ID,
                  message_id=channel_message_id,
                  text=updated_channel_text,
                  parse_mode=ParseMode.HTML
              )
          except Exception as e:
            print(f"Ошибка обновления отработанного сигнала в канале: {e}")

          final_db_status = 'CLOSED' if result_type in ['TP', 'SL'] else 'EXPIRED'
          with sqlite3.connect(DB_PATH, timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE active_signals SET status = ? WHERE signal_id = ?",
                (final_db_status, signal_id)
            )
            conn.commit()

    except Exception as e:
      print(f"Ошибка в воркере мониторинга: {e}")


# ==================== КЛАВИАТУРЫ И ИНТЕРФЕЙС ====================
def get_welcome_text(requests_left, daily_used, is_sub_active, bot_username, user_id):
  if is_sub_active:
    status_str = "🟢 <b>Безлимитная подписка активна!</b>"
  else:
    daily_left = max(0, 6 - daily_used)
    status_str = f"🎁 Осталось общих: <b>{requests_left}</b>\n⚡️ Доступно сегодня: <b>{daily_left} из 6</b>"
  ref_link = f"https://t.me/{bot_username}?start={user_id}"
  return f"""{status_str}

🤖 <b>Выберите действие ниже:</b>
Нажмите кнопку для получения сигнала по Smart Money 👇

👥 <b>Приглашайте друзей и обнуляйте лимит:</b>
Ваша реферальная ссылка:
<code>{ref_link}</code>"""


def get_main_menu_keyboard(lang="ru"):
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text=get_btn_text("signal", lang), callback_data="get_signal")],
          [InlineKeyboardButton(text=get_btn_text("how", lang), callback_data="how_it_works")],
          [InlineKeyboardButton(text=get_btn_text("payment", lang), callback_data="payment")],
      ]
  )
