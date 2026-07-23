import asyncio
import html
import json
import logging
import os
import re
import subprocess
from urllib.parse import parse_qs, urlsplit, urlunsplit

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]  # örn: "@Cebin_de_Kalsin"
OWNER_ID = int(os.environ["OWNER_ID"])
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # örn: https://cebin-de-kalsin-bot.onrender.com
# WEBHOOK_URL tanımlıysa bulut modu (Render vb.), tanımlı değilse yerel bilgisayarda
# polling modu ile çalışır. Buluta taşırken kodu değil sadece bu değişkeni eklersin.

owner_filter = filters.User(user_id=OWNER_ID)

CHOOSING, AWAITING_LINK, EDIT_CHOOSING, AWAITING_NEW_IMAGE, PREVIEW, AWAITING_NEW_TEXT = range(6)

DIRECT, EDIT, PUBLISH, CANCEL, BACK = "direct", "edit", "publish", "cancel", "back"
CHANGE_IMAGE, CHANGE_HEADING, CHANGE_TITLE, CHANGE_PRICE, CHANGE_PRICE_NOTE, CHANGE_LINK = (
    "change_image",
    "change_heading",
    "change_title",
    "change_price",
    "change_price_note",
    "change_link",
)

CHOOSING_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("1) Direkt Paylaş", callback_data=DIRECT)],
        [InlineKeyboardButton("2) Düzenleyerek Paylaş", callback_data=EDIT)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)
LINK_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔙 Geri", callback_data=BACK)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)
EDIT_CHOOSING_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🖼️Resmi değiştir", callback_data=CHANGE_IMAGE)],
        [InlineKeyboardButton("🔼Üst başlık ekle", callback_data=CHANGE_HEADING)],
        [InlineKeyboardButton("✍️Başlığı değiştir", callback_data=CHANGE_TITLE)],
        [InlineKeyboardButton("🏷️Fiyatı değiştir", callback_data=CHANGE_PRICE)],
        [InlineKeyboardButton("➡️Fiyat yanı açıklama", callback_data=CHANGE_PRICE_NOTE)],
        [InlineKeyboardButton("🔗Linki değiştir", callback_data=CHANGE_LINK)],
        [InlineKeyboardButton("🔙 Geri", callback_data=BACK)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)
BACK_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔙 Geri", callback_data=BACK)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)
PREVIEW_KEYBOARD_DIRECT = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Paylaş", callback_data=PUBLISH)],
        [InlineKeyboardButton("🔙 Geri", callback_data=BACK)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)
PREVIEW_KEYBOARD_EDIT = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Paylaş", callback_data=PUBLISH)],
        [InlineKeyboardButton("🖼️Resmi değiştir", callback_data=CHANGE_IMAGE)],
        [InlineKeyboardButton("🔼Üst başlık ekle", callback_data=CHANGE_HEADING)],
        [InlineKeyboardButton("✍️Başlığı değiştir", callback_data=CHANGE_TITLE)],
        [InlineKeyboardButton("🏷️Fiyatı değiştir", callback_data=CHANGE_PRICE)],
        [InlineKeyboardButton("➡️Fiyat yanı açıklama", callback_data=CHANGE_PRICE_NOTE)],
        [InlineKeyboardButton("🔗Linki değiştir", callback_data=CHANGE_LINK)],
        [InlineKeyboardButton("🔙 Geri", callback_data=BACK)],
        [InlineKeyboardButton("İptal", callback_data=CANCEL)],
    ]
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

META_TAG_RE = re.compile(r"<meta\s+[^>]*>", re.IGNORECASE)
PROP_RE = re.compile(r'(?:property|name)=["\']([^"\']+)["\']', re.IGNORECASE)
CONTENT_RE = re.compile(r'content=["\']([^"\']*)["\']', re.IGNORECASE)
TITLE_TAG_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
N11_SLIDER_IMG_RE = re.compile(r"<img\s+[^>]*>")
SRC_ATTR_RE = re.compile(r'\bsrc="([^"]+)"')
ALT_ATTR_RE = re.compile(r'\balt="([^"]+)"')
N11_PRICE_RE = re.compile(r'"price":"([^"]+)","priceFloat":')
N11_STORE_RE = re.compile(r'"storeName":"([^"]+)"')

MAX_CAPTION_LEN = 1024


def build_caption(content: dict) -> str:
    heading = (content.get("heading") or "").strip()
    title = (content.get("title") or "").strip()
    price = (content.get("price") or "").strip()
    price_note = (content.get("price_note") or "").strip()
    url = (content.get("url") or "").strip()

    lines = []
    if heading:
        lines.append(html.escape(heading))
        lines.append("")
    lines.append(f"📣 {html.escape(title)}" if title else "📣")
    if price:
        lines.append("")
        price_line = f"🏷️ <b>{html.escape(price)}</b>"
        if price_note:
            price_line += f" ({html.escape(price_note)})"
        lines.append(price_line)
    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{html.escape(url)}">Tıkla Git</a>')
    if (
        content.get("is_n11")
        or content.get("is_hepsiburada")
        or content.get("is_amazon")
        or content.get("is_migros")
    ):
        lines.append("")
        if content.get("is_n11"):
            platform = "N11"
        elif content.get("is_hepsiburada"):
            platform = "Hepsiburada"
        elif content.get("is_amazon"):
            platform = "Amazon"
        else:
            platform = "Migros"
        tag_line = f"🛍️#Tanıtım {platform}"
        store = (content.get("store") or "").strip()
        if store:
            tag_line += f" (Satıcı: {html.escape(store)})"
        lines.append(tag_line)
    return "\n".join(lines)[:MAX_CAPTION_LEN]


def build_whatsapp_text(content: dict) -> str:
    """WhatsApp'a kopyala-yapıştır için düz metin sürümü - HTML yerine WhatsApp'ın
    kendi *kalın* biçimini kullanır."""
    heading = (content.get("heading") or "").strip()
    title = (content.get("title") or "").strip()
    price = (content.get("price") or "").strip()
    price_note = (content.get("price_note") or "").strip()
    url = (content.get("url") or "").strip()

    lines = []
    if heading:
        lines.append(heading)
        lines.append("")
    lines.append(f"📣 {title}" if title else "📣")
    if price:
        lines.append("")
        price_line = f"🏷️ *{price}*"
        if price_note:
            price_line += f" ({price_note})"
        lines.append(price_line)
    if url:
        lines.append("")
        lines.append(f"🔗 {url}")
    if (
        content.get("is_n11")
        or content.get("is_hepsiburada")
        or content.get("is_amazon")
        or content.get("is_migros")
    ):
        lines.append("")
        if content.get("is_n11"):
            platform = "N11"
        elif content.get("is_hepsiburada"):
            platform = "Hepsiburada"
        elif content.get("is_amazon"):
            platform = "Amazon"
        else:
            platform = "Migros"
        tag_line = f"🛍️#Tanıtım {platform}"
        store = (content.get("store") or "").strip()
        if store:
            tag_line += f" (Satıcı: {store})"
        lines.append(tag_line)
    return "\n".join(lines)


def get_meta_content(page_html: str, prop_names: set) -> str | None:
    for tag in META_TAG_RE.findall(page_html):
        prop_match = PROP_RE.search(tag)
        content_match = CONTENT_RE.search(tag)
        if prop_match and content_match and prop_match.group(1).lower() in prop_names:
            value = content_match.group(1).strip()
            if value:
                return html.unescape(value)
    return None


def normalize_n11_link(url: str) -> str:
    """n11'in sl.n11.com kısa linkleri mobil uygulama yönlendirmesine (Play/App Store)
    düşüyor; www.n11.com ile aynı kod gerçek ürün sayfasına 301 yapıyor."""
    parts = urlsplit(url)
    if parts.netloc == "sl.n11.com":
        parts = parts._replace(netloc="www.n11.com")
        return urlunsplit(parts)
    return url


HB_SHORT_LINK_HOSTS = {"app.hb.biz", "hb.biz"}


def _curl_first_location(url: str, timeout: int) -> str | None:
    args = [
        "curl",
        "-s",
        "-D",
        "-",
        "-o",
        os.devnull,
        "--max-time",
        str(timeout),
        "-A",
        USER_AGENT,
        url,
    ]
    result = subprocess.run(args, capture_output=True, timeout=timeout + 5)
    headers_text = result.stdout.decode("utf-8", errors="replace")
    match = re.search(r"(?im)^location:\s*(\S+)", headers_text)
    return match.group(1).strip() if match else None


async def resolve_hepsiburada_link(url: str) -> str:
    """app.hb.biz kısa linkleri mobil uygulama yönlendirmesine (App/Play Store) düşüyor;
    ama yönlendirme zincirindeki adj_fallback parametresi gerçek ürün linkini içeriyor."""
    if urlsplit(url).netloc not in HB_SHORT_LINK_HOSTS:
        return url
    location = await asyncio.to_thread(_curl_first_location, url, 10)
    if not location:
        return url
    fallback = parse_qs(urlsplit(location).query).get("adj_fallback")
    return fallback[0] if fallback else url


YUKARIKAYDIR_HOSTS = {"www.yukarikaydir.com", "yukarikaydir.com"}


async def resolve_yukarikaydir_link(url: str) -> str:
    """yukarikaydir.com (Migros) kısa linkleri Adjust üzerinden mobil uygulamaya
    yönlendiriyor; yönlendirme zincirindeki redirect parametresi gerçek Migros linkini içeriyor."""
    if urlsplit(url).netloc not in YUKARIKAYDIR_HOSTS:
        return url
    location = await asyncio.to_thread(_curl_first_location, url, 10)
    if not location:
        return url
    fallback = parse_qs(urlsplit(location).query).get("redirect")
    return fallback[0] if fallback else url


def extract_n11_fallback(page_html: str):
    slider_idx = page_html.find('class="imageSlider"')
    if slider_idx == -1:
        return None, None
    window = page_html[slider_idx : slider_idx + 4000]
    img_match = N11_SLIDER_IMG_RE.search(window)
    if not img_match:
        return None, None
    tag = img_match.group(0)
    src_match = SRC_ATTR_RE.search(tag)
    alt_match = ALT_ATTR_RE.search(tag)
    image = src_match.group(1) if src_match else None
    if image:
        image = image.replace("/a1/375_535/", "/a1/org/")
    title = html.unescape(alt_match.group(1)) if alt_match else None
    return title, image


def extract_n11_price(page_html: str) -> str | None:
    match = N11_PRICE_RE.search(page_html)
    if match:
        return html.unescape(match.group(1).strip())
    return None


def extract_n11_store(page_html: str) -> str | None:
    match = N11_STORE_RE.search(page_html)
    if match:
        return html.unescape(match.group(1).strip()).replace("_", " ")
    return None


def format_try_price(price_val) -> str:
    try:
        value = float(price_val)
    except (TypeError, ValueError):
        return str(price_val)
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} TL"


LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def extract_hepsiburada_product(page_html: str):
    for match in LD_JSON_RE.finditer(page_html):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        candidates = []
        if isinstance(data, dict):
            if data.get("@type") == "Product":
                candidates.append(data)
            graph = data.get("@graph")
            if isinstance(graph, list):
                candidates.extend(item for item in graph if isinstance(item, dict) and item.get("@type") == "Product")

        for product in candidates:
            title = product.get("name")
            images = product.get("image")
            if isinstance(images, list) and images:
                image = images[0]
            elif isinstance(images, str):
                image = images
            else:
                image = None
            offers = product.get("offers") or {}
            price_val = offers.get("price")
            price = format_try_price(price_val) if price_val else None
            seller = (offers.get("seller") or {}).get("name") or (product.get("brand") or {}).get("name")
            if title or image:
                return title, image, price, seller
    return None, None, None, None


HB_IMAGE_URL_RE = re.compile(r'https://productimages\.hepsiburada\.net/[^\s"\'\\]+')


def extract_hepsiburada_any_image(page_html: str) -> str | None:
    """Marka işbirliği / kampanya linkleri tek bir ürün değil ürün listesi olduğu için
    Product şeması bulunmaz; bu durumda listedeki ilk ürün görselini yakalar."""
    match = HB_IMAGE_URL_RE.search(page_html)
    return match.group(0) if match else None


AMAZON_TITLE_META_RE = re.compile(r'<meta name="title" content="([^"]+)"')
# Amazon farklı sayfa şablonları sunuyor (mobil/masaüstü) - görsel her varyantta
# farklı yerde gömülü, bu yüzden birden fazla desen sırayla deneniyor.
AMAZON_IMAGE_RES = [
    re.compile(r'data-old-hires="([^"]+)"'),
    re.compile(r'"landingImageUrl":"([^"]+)"'),
    re.compile(r'"hiRes":"([^"]+)"'),
]
AMAZON_OFFSCREEN_RE = re.compile(r'class="a-offscreen">([^<]*)</span>')
# "apex-price-to-pay" sınıfı ana ürün fiyatı dışında "sıkça birlikte alınanlar" gibi
# öneri kutularında da tekrar kullanılıyor; bu yüzden asıl ürüne özgü, daha spesifik
# çapalar önce denenip en son bu genel sınıfa düşülüyor.
AMAZON_PRICE_ANCHORS = ("apex-core-price-identifier", "corePrice_feature_div", "apex-price-to-pay")
AMAZON_SELLER_RE = re.compile(
    r'a-text-bold">Gönderici / Satıcı</span>\s*</div>\s*<div[^>]*>(.*?)</div>',
    re.S,
)
AMAZON_TAG_RE = re.compile(r"<[^>]+>")
AMAZON_LINK_RE = re.compile(r'https://(?:www\.)?amazon\.com\.tr/[^\s"\'<>]+')


def extract_amazon_price(page_html: str) -> str | None:
    for anchor in AMAZON_PRICE_ANCHORS:
        idx = page_html.find(anchor)
        if idx == -1:
            continue
        window = page_html[idx : idx + 2500]
        for match in AMAZON_OFFSCREEN_RE.finditer(window):
            value = match.group(1).strip()
            if value:
                return html.unescape(value).replace("\xa0", " ")
    return None


def extract_amazon_product(page_html: str):
    title = None
    title_match = AMAZON_TITLE_META_RE.search(page_html)
    if title_match:
        raw = html.unescape(title_match.group(1))
        title = raw.split(" | ")[0].split(" : Amazon")[0].strip()

    image = None
    for pattern in AMAZON_IMAGE_RES:
        image_match = pattern.search(page_html)
        if image_match:
            image = html.unescape(image_match.group(1))
            break

    price = extract_amazon_price(page_html)

    seller = None
    seller_match = AMAZON_SELLER_RE.search(page_html)
    if seller_match:
        seller = html.unescape(AMAZON_TAG_RE.sub("", seller_match.group(1)).strip()) or None

    return title, image, price, seller


async def resolve_amazon_link(url: str) -> str:
    """fenom.io gibi affiliate kısaltıcılar yönlendirme yapmıyor, gerçek Amazon linkini
    sayfa içeriğine gömüyor; sayfayı çekip linki metinden çıkarıyoruz."""
    if urlsplit(url).netloc != "fenom.io":
        return url
    page_html = await curl_get_text(url)
    match = AMAZON_LINK_RE.search(page_html)
    return html.unescape(match.group(0)) if match else url


STATUS_MARKER = b"\n__HTTP_STATUS__:"


def _curl_get(url: str, binary: bool, timeout: int) -> bytes:
    args = [
        "curl",
        "-sL",
        "--compressed",
        "--max-time",
        str(timeout),
        "-A",
        USER_AGENT,
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "-H",
        "Accept-Language: tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "-H",
        "Referer: https://www.google.com/",
        "-H",
        "Sec-Fetch-Mode: navigate",
        "-H",
        "Sec-Fetch-Site: cross-site",
        "-H",
        "Sec-Fetch-Dest: document",
        "-w",
        "\n__HTTP_STATUS__:%{http_code}",
        url,
    ]
    result = subprocess.run(args, capture_output=True, timeout=timeout + 5)
    if result.returncode != 0:
        raise RuntimeError(
            f"curl hata verdi (kod {result.returncode}): {result.stderr.decode(errors='ignore')[:300]}"
        )
    raw = result.stdout
    idx = raw.rfind(STATUS_MARKER)
    status = None
    if idx != -1:
        status = raw[idx + len(STATUS_MARKER) :].decode(errors="ignore").strip()
        raw = raw[:idx]
    if status and not status.startswith("2"):
        snippet = raw[:400].decode("utf-8", errors="replace") if not binary else f"<binary, {len(raw)} bayt>"
        raise RuntimeError(f"HTTP {status} - yanıt: {snippet!r}")
    return raw


async def curl_get_text(url: str, timeout: int = 15) -> str:
    raw = await asyncio.to_thread(_curl_get, url, False, timeout)
    return raw.decode("utf-8", errors="replace")


async def curl_get_bytes(url: str, timeout: int = 20) -> bytes:
    return await asyncio.to_thread(_curl_get, url, True, timeout)


async def fetch_product_info(url: str):
    url = normalize_n11_link(url)
    url = await resolve_hepsiburada_link(url)
    url = await resolve_amazon_link(url)
    url = await resolve_yukarikaydir_link(url)
    is_n11 = "n11.com" in url
    is_hepsiburada = "hepsiburada.com" in url
    is_amazon = "amazon.com.tr" in url
    is_migros = "migros.com.tr" in url

    page_html = await curl_get_text(url)

    title = get_meta_content(page_html, {"og:title", "twitter:title"})
    image = get_meta_content(page_html, {"og:image", "twitter:image", "og:image:secure_url"})
    if is_migros and title:
        title = title.rsplit(" - Migros", 1)[0].strip()
    price = None
    store = None

    if is_n11:
        if not image:
            fallback_title, fallback_image = extract_n11_fallback(page_html)
            title = title or fallback_title
            image = image or fallback_image
        price = extract_n11_price(page_html)
        store = extract_n11_store(page_html)
    elif is_hepsiburada:
        hb_title, hb_image, hb_price, hb_store = extract_hepsiburada_product(page_html)
        title = title or hb_title
        image = image or hb_image
        price = hb_price
        store = hb_store
        if not image:
            image = extract_hepsiburada_any_image(page_html)
    elif is_amazon:
        am_title, am_image, am_price, am_store = extract_amazon_product(page_html)
        title = title or am_title
        image = image or am_image
        price = am_price
        store = am_store

    if not title:
        title_match = TITLE_TAG_RE.search(page_html)
        title = html.unescape(title_match.group(1).strip()) if title_match else None

    return title, image, price, store, is_n11, is_hepsiburada, is_amazon, is_migros


async def download_bytes(url: str) -> bytes:
    return await curl_get_bytes(url)


async def send_content(bot, chat_id, content, reply_markup=None):
    ctype = content["type"]
    text = content["text"]
    parse_mode = content.get("parse_mode")
    if ctype == "photo":
        await bot.send_photo(
            chat_id=chat_id, photo=content["file_id"], caption=text or None, parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    elif ctype == "video":
        await bot.send_video(
            chat_id=chat_id, video=content["file_id"], caption=text or None, parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    elif ctype == "document":
        await bot.send_document(
            chat_id=chat_id, document=content["file_id"], caption=text or None, parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    else:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)


def push_nav(context: ContextTypes.DEFAULT_TYPE, label: str) -> None:
    context.user_data.setdefault("nav_stack", []).append(label)


async def render_choosing(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(chat_id=chat_id, text="Ne yapmak istersin?", reply_markup=CHOOSING_KEYBOARD)
    return CHOOSING


async def render_link_prompt(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(
        chat_id=chat_id,
        text="Ürünün linkini gönder, görseli ve başlığı otomatik çekeceğim.",
        reply_markup=LINK_KEYBOARD,
    )
    return AWAITING_LINK


async def render_edit_choosing(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(chat_id=chat_id, text="Ne yapmak istersin?", reply_markup=EDIT_CHOOSING_KEYBOARD)
    return EDIT_CHOOSING


async def render_new_image_prompt(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(
        chat_id=chat_id, text="Yeni ürün görselini gönder.", reply_markup=BACK_CANCEL_KEYBOARD
    )
    return AWAITING_NEW_IMAGE


FIELD_PROMPTS = {
    "heading": "Eklemek istediğin üst başlığı gönder.",
    "title": "Yeni başlığı gönder.",
    "price": "Yeni fiyatı gönder.",
    "price_note": "Fiyatın yanına eklenecek açıklamayı gönder.",
    "url": "Yeni linki gönder.",
}


async def render_new_text_prompt(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("editing_field", "title")
    await context.bot.send_message(
        chat_id=chat_id, text=FIELD_PROMPTS.get(field, "Yeni metni gönder."), reply_markup=BACK_CANCEL_KEYBOARD
    )
    return AWAITING_NEW_TEXT


async def render_preview(chat_id, context: ContextTypes.DEFAULT_TYPE) -> int:
    content = context.user_data["content"]
    keyboard = PREVIEW_KEYBOARD_EDIT if context.user_data.get("mode") == "edit" else PREVIEW_KEYBOARD_DIRECT
    await send_content(context.bot, chat_id, content, reply_markup=keyboard)
    return PREVIEW


NAV_RENDERERS = {
    "choosing": render_choosing,
    "link": render_link_prompt,
    "edit_choosing": render_edit_choosing,
    "new_image": render_new_image_prompt,
    "new_text": render_new_text_prompt,
    "preview": render_preview,
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["nav_stack"] = []
    await update.effective_message.reply_text("Ne yapmak istersin?", reply_markup=CHOOSING_KEYBOARD)
    return CHOOSING


async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = "direct" if query.data == DIRECT else "edit"
    context.user_data.clear()
    context.user_data["mode"] = mode
    context.user_data["nav_stack"] = ["choosing"]
    await query.edit_message_reply_markup(reply_markup=None)
    return await render_link_prompt(query.message.chat_id, context)


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    stack = context.user_data.get("nav_stack") or []
    if not stack:
        return await cancel_callback(update, context)
    await query.answer()
    previous = stack.pop()
    await query.edit_message_reply_markup(reply_markup=None)
    return await NAV_RENDERERS[previous](query.message.chat_id, context)


FIELD_BY_CALLBACK = {
    CHANGE_HEADING: "heading",
    CHANGE_TITLE: "title",
    CHANGE_PRICE: "price",
    CHANGE_PRICE_NOTE: "price_note",
    CHANGE_LINK: "url",
}


async def edit_choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    push_nav(context, "edit_choosing")
    await query.edit_message_reply_markup(reply_markup=None)
    if query.data == CHANGE_IMAGE:
        return await render_new_image_prompt(query.message.chat_id, context)
    context.user_data["editing_field"] = FIELD_BY_CALLBACK[query.data]
    return await render_new_text_prompt(query.message.chat_id, context)


async def receive_new_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if not message.photo:
        await message.reply_text("Bir görsel gönder (fotoğraf olarak).", reply_markup=BACK_CANCEL_KEYBOARD)
        return AWAITING_NEW_IMAGE
    content = context.user_data.setdefault("content", {"type": "photo", "text": "", "parse_mode": None})
    content["type"] = "photo"
    content["file_id"] = message.photo[-1].file_id
    push_nav(context, "new_image")
    return await render_preview(message.chat_id, context)


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = (update.effective_message.text or "").strip()
    if not url.startswith(("http://", "https://")):
        await update.effective_message.reply_text(
            "Bu bir link'e benzemiyor, geçerli bir ürün linki gönder.", reply_markup=LINK_KEYBOARD
        )
        return AWAITING_LINK

    status_msg = await update.effective_message.reply_text("Ürün bilgisi çekiliyor...")

    try:
        title, image_url, price, store, is_n11, is_hepsiburada, is_amazon, is_migros = await fetch_product_info(url)
    except Exception:
        logger.exception("Ürün sayfası çekilemedi: %s", url)
        await status_msg.edit_text(
            "Bu linkten ürün bilgisi çekilemedi. Başka bir link deneyebilirsin.", reply_markup=LINK_KEYBOARD
        )
        return AWAITING_LINK

    if not image_url:
        await status_msg.edit_text(
            "Bu linkte ürün görseli bulunamadı. Başka bir link deneyebilirsin.", reply_markup=LINK_KEYBOARD
        )
        return AWAITING_LINK

    content = {
        "type": "photo",
        "title": (title.strip()[:300] if title else ""),
        "price": (price.strip() if price else ""),
        "url": url,
        "is_n11": is_n11,
        "is_hepsiburada": is_hepsiburada,
        "is_amazon": is_amazon,
        "is_migros": is_migros,
        "store": store or "",
        "parse_mode": ParseMode.HTML,
    }
    content["text"] = build_caption(content)

    is_edit_mode = context.user_data.get("mode") == "edit"
    next_keyboard = EDIT_CHOOSING_KEYBOARD if is_edit_mode else PREVIEW_KEYBOARD_DIRECT

    try:
        image_bytes = await download_bytes(image_url)
        preview_message = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image_bytes,
            caption=content["text"],
            parse_mode=ParseMode.HTML,
            reply_markup=next_keyboard,
        )
    except Exception:
        logger.exception("Önizleme gönderilemedi")
        await status_msg.edit_text(
            "Görsel indirilemedi/gösterilemedi. Başka bir link deneyebilirsin.", reply_markup=LINK_KEYBOARD
        )
        return AWAITING_LINK

    content["file_id"] = preview_message.photo[-1].file_id
    context.user_data["content"] = content
    await status_msg.delete()
    push_nav(context, "link")

    return EDIT_CHOOSING if is_edit_mode else PREVIEW


async def preview_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == PUBLISH:
        content = context.user_data.get("content")
        try:
            await send_content(context.bot, CHANNEL_ID, content)
            await query.edit_message_caption(caption="Kanala paylaşıldı.")
            whatsapp_text = html.escape(build_whatsapp_text(content))
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📋 WhatsApp için hazır metin (görseli de indirip ekle):",
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"<code>{whatsapp_text}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("Kanala paylaşım başarısız")
            await query.edit_message_caption(caption="Paylaşım başarısız oldu, logları kontrol et.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data == CHANGE_IMAGE:
        push_nav(context, "preview")
        await query.edit_message_reply_markup(reply_markup=None)
        return await render_new_image_prompt(query.message.chat_id, context)

    if query.data in (CHANGE_HEADING, CHANGE_TITLE, CHANGE_PRICE, CHANGE_PRICE_NOTE, CHANGE_LINK):
        push_nav(context, "preview")
        context.user_data["editing_field"] = FIELD_BY_CALLBACK[query.data]
        await query.edit_message_reply_markup(reply_markup=None)
        return await render_new_text_prompt(query.message.chat_id, context)

    await query.edit_message_caption(caption="İptal edildi.")
    context.user_data.clear()
    return ConversationHandler.END


async def receive_new_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("editing_field", "title")
    content = context.user_data["content"]
    content[field] = update.effective_message.text or ""
    content["text"] = build_caption(content)
    push_nav(context, "new_text")
    return await render_preview(update.effective_message.chat_id, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text("İptal edildi.")
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await context.bot.send_message(chat_id=query.message.chat_id, text="İptal edildi.")
    return ConversationHandler.END


async def stale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user is None or update.effective_user.id != OWNER_ID:
        await query.answer()
        return
    await query.answer("Bu önizleme artık geçerli değil.", show_alert=True)
    try:
        await query.edit_message_text("Bu önizlemenin süresi doldu. /start ile yeniden başlat.")
    except Exception:
        pass


def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start, filters=owner_filter)],
        states={
            CHOOSING: [
                CallbackQueryHandler(choose_mode, pattern=f"^({DIRECT}|{EDIT})$"),
                CallbackQueryHandler(cancel_callback, pattern=f"^{CANCEL}$"),
            ],
            AWAITING_LINK: [
                MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, receive_link),
                CallbackQueryHandler(back_callback, pattern=f"^{BACK}$"),
                CallbackQueryHandler(cancel_callback, pattern=f"^{CANCEL}$"),
            ],
            EDIT_CHOOSING: [
                CallbackQueryHandler(
                    edit_choose_mode,
                    pattern=(
                        f"^({CHANGE_IMAGE}|{CHANGE_HEADING}|{CHANGE_TITLE}|"
                        f"{CHANGE_PRICE}|{CHANGE_PRICE_NOTE}|{CHANGE_LINK})$"
                    ),
                ),
                CallbackQueryHandler(back_callback, pattern=f"^{BACK}$"),
                CallbackQueryHandler(cancel_callback, pattern=f"^{CANCEL}$"),
            ],
            AWAITING_NEW_IMAGE: [
                MessageHandler(owner_filter & filters.PHOTO, receive_new_image),
                CallbackQueryHandler(back_callback, pattern=f"^{BACK}$"),
                CallbackQueryHandler(cancel_callback, pattern=f"^{CANCEL}$"),
            ],
            PREVIEW: [
                CallbackQueryHandler(
                    preview_action,
                    pattern=(
                        f"^({PUBLISH}|{CHANGE_IMAGE}|{CHANGE_HEADING}|{CHANGE_TITLE}|"
                        f"{CHANGE_PRICE}|{CHANGE_PRICE_NOTE}|{CHANGE_LINK}|{CANCEL})$"
                    ),
                ),
                CallbackQueryHandler(back_callback, pattern=f"^{BACK}$"),
            ],
            AWAITING_NEW_TEXT: [
                MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, receive_new_text),
                CallbackQueryHandler(back_callback, pattern=f"^{BACK}$"),
                CallbackQueryHandler(cancel_callback, pattern=f"^{CANCEL}$"),
            ],
        },
        fallbacks=[CommandHandler("iptal", cancel, filters=owner_filter)],
        allow_reentry=True,
    )
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(stale_callback))

    if WEBHOOK_URL:
        logger.info("Bulut modu (webhook) ile başlatılıyor: %s", WEBHOOK_URL)
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook",
        )
    else:
        logger.info("Yerel mod (polling) ile başlatılıyor")
        application.run_polling()


if __name__ == "__main__":
    main()
