import os
import logging
import time
from collections import defaultdict
from functools import wraps
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatAction,
)
from telegram.ext import (
    Updater,
    MessageHandler,
    Filters,
    CallbackContext,
    CommandHandler,
    CallbackQueryHandler,
)
import openai

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG / LOGS
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("Mad2MoiBot")

# Tokens / clés
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.warning("⚠️  OPENAI_API_KEY non défini — IA désactivée")
else:
    openai.api_key = OPENAI_API_KEY
    logger.info("✅ OPENAI_API_KEY chargée")

# URLs
M2M_BASE_URL = "https://www.mad2moi.com/"
FB_MAD2MOI_URL = "https://www.facebook.com/groups/1095227448813415/?ref=share"
M2M_CAMPAIGN = "non_vax_groupe"

# ═══════════════════════════════════════════════════════════════════════════════
# STOCKAGE EN MÉMOIRE
# ═══════════════════════════════════════════════════════════════════════════════

user_conversations = defaultdict(list)
MAX_HISTORY = 5

user_last_messages = defaultdict(list)
RATE_LIMIT_MESSAGES = 5
RATE_LIMIT_WINDOW = 60

# Anti-spam présentations : évite de répondre 2x au même user
users_welcomed_presentation = set()

stats = {
    "total_private_messages": 0,
    "total_ai_responses": 0,
    "total_new_members": 0,
    "total_presentations": 0,
    "button_clicks": defaultdict(int),
}

# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════════

KEYWORDS_RENCONTRE = [
    "rencontrer", "rencontre", "célibataire", "copine", "copain",
    "cherche une fille", "cherche un mec", "envie de rencontrer",
    "seul", "seule", "solitude", "trouver quelqu'un", "âme sœur",
]

KEYWORDS_PRESENTATION = [
    "je m'appelle", "moi c'est", "mon prénom", "j'habite", "je suis de",
    "je vis à", "je vis en", "je cherche", "enchanté", "enchantée",
    "bonjour à tous", "hello tout le monde", "salut à tous",
    "nouveau ici", "nouvelle ici", "je me présente", "petite présentation",
    "je suis nouveau", "je suis nouvelle", "ravi de rejoindre",
    "j'ai", "ans", "région", "département",
]

# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT IA
# ═══════════════════════════════════════════════════════════════════════════════

AI_SYSTEM_PROMPT = """Tu es une conseillère bienveillante pour Mad2Moi, un site de rencontres pour personnes libres et éveillées.

🎯 TON RÔLE :
• Écouter et comprendre (solitude, décalage, rejet, besoin de liens authentiques)
• Donner des conseils concrets sur la vie sociale et amoureuse
• Rassurer : la personne n'est pas seule, une communauté alignée existe
• Orienter vers Mad2Moi naturellement

📏 RÈGLES :
• Ton chaleureux, humain, direct, jamais condescendant
• JAMAIS de conseils médicaux, financiers ou juridiques
• Pas de contenu sexuel explicite
• Pas de promesses miracles, parle de possibilités
• Réponses courtes : 5-10 lignes max, faciles à lire
• Utilise des emojis avec parcimonie (1-2 max)

🔥 CALL TO ACTION (2 réponses sur 3) :
Termine par une invitation naturelle vers Mad2Moi :
• "Pour passer du virtuel au réel → https://www.mad2moi.com/"
• "Le plus simple pour rencontrer des gens alignés : https://www.mad2moi.com/"
• "Crée ton profil sur Mad2Moi : https://www.mad2moi.com/"

⚠️ Si question hors-sujet, réponds brièvement puis ramène vers les rencontres et Mad2Moi."""

# ═══════════════════════════════════════════════════════════════════════════════
# TEXTES OPTIMISÉS CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════

# Message PUBLIC groupe - COURT et PERCUTANT
WELCOME_PUBLIC = """👋 Bienvenue !

Tu es ici pour rencontrer des gens libres et éveillés.

🔥 Crée ton profil (bouton ci-dessous)
💬 Besoin d'aide ? @mad2moi_helper_bot

Présente-toi quand tu veux ✨"""

# Réponse quand quelqu'un se présente
WELCOME_PRESENTATION = """🙌 Bienvenue {name} !

Content de te voir parmi nous. Pour passer aux rencontres concrètes :"""

# Message DM après /start
WELCOME_DM = """👋 Salut !

Je suis là pour t'aider à rencontrer des personnes alignées avec tes valeurs.

🔥 Inscription rapide → bouton ci-dessous

Ou dis-moi ce que tu cherches, je te guide 👇"""

# Relances DM
FOLLOWUP_MESSAGES = [
    # 24h
    """👋 Re !

Tu as vu Mad2Moi ? C'est là que ça se passe pour les vraies rencontres.

Inscription gratuite et rapide :""",
    # 72h
    """💭 Hello !

Des centaines de membres ont déjà trouvé des personnes alignées sur Mad2Moi.

Et toi, tu te lances ? 👇""",
    # 7 jours
    """🌟 Coucou !

De nouvelles personnes rejoignent Mad2Moi chaque jour près de chez toi.

Peut-être que ton match t'attend ? 👇""",
]

RATE_LIMIT_MSG = """⏳ Doucement ! Attends une minute avant de continuer 😊"""

MEDIA_RESPONSE = """📸 Je ne lis que le texte pour l'instant.

Dis-moi ce que tu recherches ! En attendant : https://www.mad2moi.com/"""

ABOUT_TEXT = """ℹ️ **Mad2Moi**

Plateforme de rencontres pour personnes libres et authentiques.

✅ Gratuit
✅ Bienveillant
✅ Sans censure

👉 https://www.mad2moi.com/"""

RESET_CONFIRM = """🔄 C'est reparti à zéro !

Dis-moi ce que tu cherches 👇"""

HELP_TEXT = """🤖 **Commandes**

/start - Démarrer
/inscription - Lien Mad2Moi
/about - En savoir plus
/reset - Réinitialiser
/help - Aide

Écris-moi librement, je réponds 💬"""

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════


def make_m2m_url(step=""):
    """URL Mad2Moi avec UTM."""
    url = f"{M2M_BASE_URL}?utm_source=telegram&utm_medium=bot&utm_campaign={M2M_CAMPAIGN}"
    if step:
        url += f"&utm_content={step}"
    return url


def m2m_keyboard_main(step):
    """Clavier principal : CTA fort + Facebook secondaire."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Rencontrer des gens comme moi", url=make_m2m_url(step))],
        [InlineKeyboardButton("📣 Groupe Facebook", url=FB_MAD2MOI_URL)],
    ])


def m2m_keyboard_simple(step):
    """Clavier simple : juste le CTA Mad2Moi."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Rencontrer des gens comme moi", url=make_m2m_url(step))],
    ])


def menu_keyboard():
    """Menu DM."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💘 Rencontres", callback_data="menu_rencontres")],
        [InlineKeyboardButton("🤝 Amitié", callback_data="menu_amitie")],
        [InlineKeyboardButton("👀 Je découvre", callback_data="menu_decouverte")],
    ])


def is_rate_limited(user_id):
    """Rate limiting."""
    now = time.time()
    user_last_messages[user_id] = [
        t for t in user_last_messages[user_id]
        if now - t < RATE_LIMIT_WINDOW
    ]
    if len(user_last_messages[user_id]) >= RATE_LIMIT_MESSAGES:
        return True
    user_last_messages[user_id].append(now)
    return False


def send_typing(context, chat_id):
    """Indicateur 'écrit...'"""
    try:
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass


def log_handler(func):
    """Décorateur logging."""
    @wraps(func)
    def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        handler_name = func.__name__
        logger.info(f"[{handler_name}] user={user.id if user else '?'} chat={chat.type if chat else '?'}")
        try:
            return func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{handler_name}] ERREUR: {e}")
            raise
    return wrapper


def is_presentation(text):
    """Détecte si un message est une présentation."""
    text_lower = text.lower()
    keyword_count = sum(1 for k in KEYWORDS_PRESENTATION if k in text_lower)
    
    # Présentation si : 2+ keywords OU (1 keyword ET message long)
    return keyword_count >= 2 or (keyword_count >= 1 and len(text) > 80)


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════════


@log_handler
def welcome_new_members(update, context):
    """Message PUBLIC quand quelqu'un rejoint."""
    message = update.message
    chat = message.chat

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue

        stats["total_new_members"] += 1
        logger.info(f"📥 Nouveau: {new_member.first_name} (total: {stats['total_new_members']})")

        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=WELCOME_PUBLIC,
                reply_markup=m2m_keyboard_main("welcome"),
            )
        except Exception as e:
            logger.warning(f"Erreur welcome: {e}")


def schedule_followups(context, user_id):
    """Programme les relances DM."""
    delays = [
        (24 * 60 * 60, 0),
        (72 * 60 * 60, 1),
        (7 * 24 * 60 * 60, 2),
    ]
    for delay, idx in delays:
        try:
            context.job_queue.run_once(
                lambda ctx, i=idx: send_followup(ctx, i),
                when=delay,
                context=user_id,
                name=f"followup_{user_id}_{idx}",
            )
        except Exception as e:
            logger.warning(f"Erreur schedule followup {idx}: {e}")


def send_followup(context, msg_index):
    """Envoie une relance."""
    user_id = context.job.context
    try:
        context.bot.send_message(
            chat_id=user_id,
            text=FOLLOWUP_MESSAGES[msg_index],
            reply_markup=m2m_keyboard_simple(f"followup_{msg_index}"),
        )
        logger.info(f"📤 Follow-up {msg_index} → {user_id}")
    except Exception as e:
        logger.warning(f"Erreur followup {msg_index}: {e}")


@log_handler
def cmd_start(update, context):
    """/start"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type in ("group", "supergroup"):
        try:
            context.bot.send_message(
                chat_id=chat.id,
                text="📩 En privé → https://t.me/mad2moi_helper_bot?start=go",
            )
        except Exception as e:
            logger.warning(f"Erreur /start groupe: {e}")
        return

    send_typing(context, chat.id)
    user_conversations[user.id] = []

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=WELCOME_DM,
            reply_markup=m2m_keyboard_simple("dm_start"),
        )
        context.bot.send_message(
            chat_id=chat.id,
            text="Qu'est-ce qui t'amène ? 👇",
            reply_markup=menu_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Erreur /start DM: {e}")

    schedule_followups(context, user.id)


@log_handler
def cmd_help(update, context):
    """/help"""
    chat = update.effective_chat
    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=HELP_TEXT,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard_simple("help"),
        )
    except Exception as e:
        logger.warning(f"Erreur /help: {e}")


@log_handler
def cmd_inscription(update, context):
    """/inscription"""
    chat = update.effective_chat
    stats["button_clicks"]["cmd_inscription"] += 1

    text = f"""🚀 **Inscris-toi maintenant !**

👉 {make_m2m_url("cmd_inscription")}

Gratuit, rapide, sécurisé ✅"""

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard_simple("cmd_inscription"),
        )
    except Exception as e:
        logger.warning(f"Erreur /inscription: {e}")


@log_handler
def cmd_about(update, context):
    """/about"""
    chat = update.effective_chat
    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=ABOUT_TEXT,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard_simple("about"),
        )
    except Exception as e:
        logger.warning(f"Erreur /about: {e}")


@log_handler
def cmd_reset(update, context):
    """/reset"""
    user = update.effective_user
    chat = update.effective_chat
    user_conversations[user.id] = []

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=RESET_CONFIRM,
            reply_markup=menu_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Erreur /reset: {e}")


@log_handler
def menu_callback(update, context):
    """Boutons menu."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    query.answer()
    stats["button_clicks"][data] += 1

    responses = {
        "menu_rencontres": "💘 Parfait ! Pour les rencontres, c'est par ici :",
        "menu_amitie": "🤝 Top ! Tu trouveras des amis alignés ici :",
        "menu_decouverte": "👀 Prends ton temps. Quand tu es prêt(e) :",
    }

    txt = responses.get(data, responses["menu_decouverte"])
    step = data.replace("menu_", "")

    try:
        context.bot.send_message(
            chat_id=user_id,
            text=txt,
            reply_markup=m2m_keyboard_simple(step),
        )
    except Exception as e:
        logger.warning(f"Erreur callback: {e}")


@log_handler
def group_message_handler(update, context):
    """Gère TOUS les messages groupe : présentations ET keywords."""
    message = update.message
    user = message.from_user
    
    if user.is_bot:
        return
    
    text = message.text or ""
    if not text:
        return
    
    text_lower = text.lower()
    
    # 1. Vérifier si c'est une PRÉSENTATION (prioritaire)
    if is_presentation(text) and user.id not in users_welcomed_presentation:
        users_welcomed_presentation.add(user.id)
        stats["total_presentations"] += 1
        
        name = user.first_name or "toi"
        logger.info(f"📝 Présentation: {name} (total: {stats['total_presentations']})")
        
        try:
            message.reply_text(
                WELCOME_PRESENTATION.format(name=name),
                reply_markup=m2m_keyboard_simple("presentation"),
            )
        except Exception as e:
            logger.warning(f"Erreur reply présentation: {e}")
        return
    
    # 2. Sinon, vérifier les KEYWORDS rencontre
    if any(k in text_lower for k in KEYWORDS_RENCONTRE):
        logger.info(f"🔑 Keyword: '{text[:30]}...'")
        try:
            message.reply_text(
                "💡 Pour de vraies rencontres →",
                reply_markup=m2m_keyboard_simple("keyword"),
            )
        except Exception as e:
            logger.warning(f"Erreur keyword reply: {e}")


@log_handler
def handle_media(update, context):
    """Médias en DM."""
    chat = update.effective_chat
    if chat.type != "private":
        return

    try:
        context.bot.send_message(chat_id=chat.id, text=MEDIA_RESPONSE)
    except Exception as e:
        logger.warning(f"Erreur média: {e}")


@log_handler
def private_ai_chat(update, context):
    """IA en DM."""
    message = update.message
    chat = message.chat
    user = message.from_user

    user_text = (message.text or "").strip()
    if not user_text:
        return

    stats["total_private_messages"] += 1

    if is_rate_limited(user.id):
        logger.warning(f"⚠️ Rate limit: {user.id}")
        try:
            message.reply_text(RATE_LIMIT_MSG)
        except Exception:
            pass
        return

    send_typing(context, chat.id)

    if not OPENAI_API_KEY:
        try:
            message.reply_text(
                "Je ne peux pas utiliser l'IA maintenant.\n\n"
                "Découvre Mad2Moi : https://www.mad2moi.com/"
            )
        except Exception as e:
            logger.warning(f"Erreur fallback: {e}")
        return

    user_conversations[user.id].append({"role": "user", "content": user_text})

    if len(user_conversations[user.id]) > MAX_HISTORY * 2:
        user_conversations[user.id] = user_conversations[user.id][-MAX_HISTORY * 2:]

    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
    messages.extend(user_conversations[user.id])

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
            presence_penalty=0.3,
            frequency_penalty=0.3,
        )
        answer = completion.choices[0].message["content"].strip()
        stats["total_ai_responses"] += 1
        user_conversations[user.id].append({"role": "assistant", "content": answer})
        logger.info(f"✅ IA ({len(answer)} chars) - Total: {stats['total_ai_responses']}")

    except openai.error.RateLimitError:
        logger.error("❌ OpenAI rate limit")
        answer = "Je suis débordée 😅\n\nDécouvre Mad2Moi : https://www.mad2moi.com/"
    except openai.error.APIError as e:
        logger.error(f"❌ OpenAI API: {e}")
        answer = "Souci technique…\n\nMad2Moi : https://www.mad2moi.com/"
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        answer = "Je n'arrive pas à répondre.\n\nMad2Moi : https://www.mad2moi.com/"

    try:
        message.reply_text(answer)
    except Exception as e:
        logger.warning(f"Erreur envoi: {e}")


@log_handler
def cmd_stats(update, context):
    """/stats (admin)"""
    user = update.effective_user
    chat = update.effective_chat

    admin_ids_str = os.environ.get("ADMIN_IDS", "")
    ADMIN_IDS = [int(x) for x in admin_ids_str.split(",") if x.strip()]

    if user.id not in ADMIN_IDS:
        return

    stats_text = f"""📊 **Stats Mad2Moi Bot**

👥 Nouveaux membres: {stats['total_new_members']}
📝 Présentations: {stats['total_presentations']}
💬 Messages privés: {stats['total_private_messages']}
🤖 Réponses IA: {stats['total_ai_responses']}
👆 Clics: {dict(stats['button_clicks'])}

🧠 Users mémoire: {len(user_conversations)}
🎉 Users présentés: {len(users_welcomed_presentation)}"""

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=stats_text,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Erreur /stats: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # 1. Nouveaux membres
    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        welcome_new_members
    ))

    # 2. Commandes
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("inscription", cmd_inscription))
    dp.add_handler(CommandHandler("about", cmd_about))
    dp.add_handler(CommandHandler("reset", cmd_reset))
    dp.add_handler(CommandHandler("stats", cmd_stats))

    # 3. Boutons callback
    dp.add_handler(CallbackQueryHandler(menu_callback))

    # 4. Messages groupe (présentations + keywords)
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.chat_type.groups,
        group_message_handler
    ))

    # 5. Médias en privé
    dp.add_handler(MessageHandler(
        (Filters.photo | Filters.voice | Filters.video | Filters.document)
        & Filters.chat_type.private,
        handle_media
    ))

    # 6. IA en privé
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.chat_type.private,
        private_ai_chat
    ))

    logger.info("=" * 50)
    logger.info("🚀 Mad2Moi Bot v2.0 - Optimisé Conversion")
    logger.info(f"   OpenAI: {'✅' if OPENAI_API_KEY else '❌'}")
    logger.info(f"   Rate limit: {RATE_LIMIT_MESSAGES}/{RATE_LIMIT_WINDOW}s")
    logger.info(f"   Historique: {MAX_HISTORY} msg")
    logger.info(f"   Keywords présentation: {len(KEYWORDS_PRESENTATION)}")
    logger.info("=" * 50)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
