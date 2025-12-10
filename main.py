import os
import logging
import time
from datetime import datetime
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
# STOCKAGE EN MÉMOIRE (conversations, rate limiting, stats)
# ═══════════════════════════════════════════════════════════════════════════════

# Historique des conversations par user_id (pour contexte OpenAI)
user_conversations = defaultdict(list)
MAX_HISTORY = 5  # Nombre de messages à garder en contexte

# Rate limiting : timestamps des derniers messages par user
user_last_messages = defaultdict(list)
RATE_LIMIT_MESSAGES = 5  # Max messages
RATE_LIMIT_WINDOW = 60   # Par minute

# Stats simples
stats = {
    "total_private_messages": 0,
    "total_ai_responses": 0,
    "total_new_members": 0,
    "button_clicks": defaultdict(int),
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT IA OPTIMISÉ
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
Termine par une invitation naturelle vers Mad2Moi, exemples :
• "Pour passer du virtuel au réel → https://www.mad2moi.com/"
• "Le plus simple pour rencontrer des gens alignés : https://www.mad2moi.com/"
• "Crée ton profil sur Mad2Moi, c'est là que ça se passe : https://www.mad2moi.com/"

⚠️ Si la personne pose une question hors-sujet (météo, recette, etc.), réponds brièvement puis ramène vers le sujet principal : les rencontres et Mad2Moi."""

# ═══════════════════════════════════════════════════════════════════════════════
# TEXTES & MESSAGES
# ═══════════════════════════════════════════════════════════════════════════════

WELCOME_PUBLIC = """👋 Bienvenue parmi nous !

Tu es dans un groupe 100% bienveillant pour personnes libres, éveillées et non-injectées.

🔥 Pour faire de vraies rencontres → Mad2Moi (bouton ci-dessous)

📩 Écris-moi en privé @mad2moi_helper_bot pour recevoir tous les liens utiles.

Présente-toi quand tu veux : prénom, région, ce que tu cherches ✨"""

WELCOME_DM = """👋 Salut et bienvenue !

Je suis l'assistant Mad2Moi. Ici, tu peux :
• Me poser des questions sur les rencontres
• Découvrir la communauté Mad2Moi
• Obtenir des conseils personnalisés

🔥 Pour t'inscrire directement → bouton ci-dessous

Dis-moi ta région et ce que tu recherches, je t'aide à t'orienter 👇"""

FOLLOWUP_MESSAGES = [
    # 24h
    """👋 Re-bonjour !

Tu as eu le temps de découvrir Mad2Moi ? C'est là que les membres font de vraies rencontres (amicales, amoureuses, projets…).

Inscription rapide et sécurisée ici :""",
    # 72h
    """💭 Salut, c'est le bot Mad2Moi.

Je voulais juste te rappeler que si tu cherches à rencontrer des personnes éveillées et bienveillantes, Mad2Moi est fait pour ça.

Des milliers de membres t'attendent déjà :""",
    # 7 jours
    """🌟 Hello !

Ça fait quelques jours qu'on ne s'est pas parlé. Si tu n'as pas encore franchi le pas, sache que de nouvelles personnes rejoignent Mad2Moi chaque jour.

Peut-être que ton match t'attend déjà ? 👇""",
]

RATE_LIMIT_MSG = """⏳ Doucement ! Tu m'envoies beaucoup de messages.

Attends une minute avant de continuer, je reste disponible 😊"""

MEDIA_RESPONSE = """📸 J'ai bien reçu ton message, mais je ne peux analyser que du texte pour l'instant.

Dis-moi ce que tu recherches ou pose-moi une question, je suis là pour t'aider !

En attendant, tu peux découvrir Mad2Moi ici : https://www.mad2moi.com/"""

ABOUT_TEXT = """ℹ️ **À propos de Mad2Moi**

Mad2Moi est une plateforme de rencontres pour personnes libres, éveillées et authentiques.

✅ Inscription gratuite
✅ Communauté bienveillante
✅ Sans censure ni jugement
✅ Rencontres amicales & amoureuses

👉 https://www.mad2moi.com/"""

RESET_CONFIRM = """🔄 Conversation réinitialisée !

On repart de zéro. Dis-moi ce que tu recherches 👇"""

KEYWORDS_RENCONTRE = [
    "rencontrer", "rencontre", "célibataire", "copine", "copain",
    "cherche une fille", "cherche un mec", "envie de rencontrer",
    "seul", "seule", "solitude", "trouver quelqu'un", "âme sœur",
]

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════


def make_m2m_url(step=""):
    """Génère URL Mad2Moi avec UTM tracking."""
    url = f"{M2M_BASE_URL}?utm_source=telegram&utm_medium=bot&utm_campaign={M2M_CAMPAIGN}"
    if step:
        url += f"&utm_content={step}"
    return url


def m2m_keyboard(step):
    """Clavier inline avec boutons Mad2Moi + Facebook."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Rejoindre Mad2Moi", url=make_m2m_url(step))],
        [InlineKeyboardButton("📣 Groupe Facebook", url=FB_MAD2MOI_URL)],
    ])


def menu_keyboard():
    """Menu principal en DM."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💘 Je cherche des rencontres", callback_data="menu_rencontres")],
        [InlineKeyboardButton("🤝 Je veux lier amitié", callback_data="menu_amitie")],
        [InlineKeyboardButton("👀 Je découvre", callback_data="menu_decouverte")],
    ])


def is_rate_limited(user_id):
    """Vérifie si l'utilisateur dépasse le rate limit."""
    now = time.time()
    # Nettoyer les anciens timestamps
    user_last_messages[user_id] = [
        t for t in user_last_messages[user_id]
        if now - t < RATE_LIMIT_WINDOW
    ]
    # Vérifier la limite
    if len(user_last_messages[user_id]) >= RATE_LIMIT_MESSAGES:
        return True
    # Enregistrer ce message
    user_last_messages[user_id].append(now)
    return False


def send_typing(context, chat_id):
    """Envoie l'indicateur 'en train d'écrire...'"""
    try:
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass


def log_handler(func):
    """Décorateur pour logger les handlers automatiquement."""
    @wraps(func)
    def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        handler_name = func.__name__
        logger.info(f"[{handler_name}] user={user.id if user else '?'} chat_type={chat.type if chat else '?'}")
        try:
            return func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{handler_name}] ERREUR: {e}")
            raise
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════════


@log_handler
def welcome_new_members(update, context):
    """Message PUBLIC quand quelqu'un rejoint le groupe."""
    message = update.message
    chat = message.chat
    keyboard = m2m_keyboard("welcome_public")

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue

        stats["total_new_members"] += 1
        logger.info(f"📥 Nouveau membre: {new_member.first_name} (total: {stats['total_new_members']})")

        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=WELCOME_PUBLIC,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"Erreur welcome public: {e}")


def schedule_followups(context, user_id):
    """Programme les 3 relances automatiques."""
    delays = [
        (24 * 60 * 60, 0),      # 24h
        (72 * 60 * 60, 1),      # 72h
        (7 * 24 * 60 * 60, 2),  # 7 jours
    ]
    for delay, msg_index in delays:
        try:
            context.job_queue.run_once(
                lambda ctx, idx=msg_index: send_followup(ctx, idx),
                when=delay,
                context=user_id,
                name=f"followup_{user_id}_{msg_index}",
            )
        except Exception as e:
            logger.warning(f"Erreur programmation followup {msg_index}: {e}")


def send_followup(context, msg_index):
    """Envoie une relance programmée."""
    user_id = context.job.context
    keyboard = m2m_keyboard(f"followup_{msg_index}")
    try:
        context.bot.send_message(
            chat_id=user_id,
            text=FOLLOWUP_MESSAGES[msg_index],
            reply_markup=keyboard,
        )
        logger.info(f"📤 Follow-up {msg_index} envoyé à {user_id}")
    except Exception as e:
        logger.warning(f"Erreur follow-up {msg_index}: {e}")


@log_handler
def cmd_start(update, context):
    """/start : accueil en privé ou redirection depuis groupe."""
    chat = update.effective_chat
    user = update.effective_user

    # Dans un groupe → renvoyer vers le privé
    if chat.type in ("group", "supergroup"):
        try:
            context.bot.send_message(
                chat_id=chat.id,
                text="📩 Pour discuter en privé → https://t.me/mad2moi_helper_bot?start=go",
            )
        except Exception as e:
            logger.warning(f"Erreur /start groupe: {e}")
        return

    # En privé → tunnel d'accueil
    send_typing(context, chat.id)

    # Reset conversation
    user_conversations[user.id] = []

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=WELCOME_DM,
            reply_markup=m2m_keyboard("welcome_dm"),
        )
        context.bot.send_message(
            chat_id=chat.id,
            text="Dis-moi ce que tu cherches 👇",
            reply_markup=menu_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Erreur /start privé: {e}")

    # Programmer les relances
    schedule_followups(context, user.id)


@log_handler
def cmd_help(update, context):
    """/help : aide rapide."""
    chat = update.effective_chat
    help_text = """🤖 **Commandes disponibles**

/start - Démarrer la conversation
/inscription - Lien direct vers Mad2Moi
/about - En savoir plus sur Mad2Moi
/reset - Réinitialiser notre conversation
/help - Afficher cette aide

Tu peux aussi m'écrire librement, je te réponds avec l'IA 💬"""

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=help_text,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard("help"),
        )
    except Exception as e:
        logger.warning(f"Erreur /help: {e}")


@log_handler
def cmd_inscription(update, context):
    """/inscription : lien direct."""
    chat = update.effective_chat
    stats["button_clicks"]["cmd_inscription"] += 1

    text = """🚀 **Inscris-toi maintenant sur Mad2Moi !**

👉 https://www.mad2moi.com/?utm_source=telegram&utm_medium=bot&utm_campaign=non_vax_groupe&utm_content=cmd_inscription

C'est gratuit, rapide et sécurisé ✅"""

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard("cmd_inscription"),
        )
    except Exception as e:
        logger.warning(f"Erreur /inscription: {e}")


@log_handler
def cmd_about(update, context):
    """/about : informations sur Mad2Moi."""
    chat = update.effective_chat
    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=ABOUT_TEXT,
            parse_mode="Markdown",
            reply_markup=m2m_keyboard("about"),
        )
    except Exception as e:
        logger.warning(f"Erreur /about: {e}")


@log_handler
def cmd_reset(update, context):
    """/reset : réinitialise la conversation."""
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
    """Gestion des boutons du menu."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    query.answer()
    stats["button_clicks"][data] += 1

    responses = {
        "menu_rencontres": (
            "💘 Parfait ! Pour les rencontres, le plus simple est de t'inscrire sur Mad2Moi.\n\n"
            "Tu y trouveras des personnes qui pensent comme toi, sans censure :"
        ),
        "menu_amitie": (
            "🤝 Tu veux élargir ton cercle d'amis éveillés, c'est top !\n\n"
            "Mad2Moi permet aussi de créer des liens amicaux. Inscris-toi ici :"
        ),
        "menu_decouverte": (
            "👀 Prends ton temps pour découvrir…\n\n"
            "Quand tu seras prêt(e), crée ton profil sur Mad2Moi :"
        ),
    }

    txt = responses.get(data, responses["menu_decouverte"])
    step = data.replace("menu_", "")

    try:
        context.bot.send_message(
            chat_id=user_id,
            text=txt,
            reply_markup=m2m_keyboard(step),
        )
    except Exception as e:
        logger.warning(f"Erreur callback menu: {e}")


@log_handler
def keyword_auto_reply(update, context):
    """Auto-réponse dans les GROUPES sur mots-clés."""
    message = update.message
    user = message.from_user

    if user.is_bot:
        return

    text = (message.text or "").lower()

    if any(k in text for k in KEYWORDS_RENCONTRE):
        logger.info(f"🔑 Keyword détecté: '{text[:40]}...'")
        reply = (
            "💡 Pour faire de vraies rencontres avec des personnes éveillées, "
            "le plus simple → Mad2Moi :"
        )
        try:
            message.reply_text(reply, reply_markup=m2m_keyboard("keyword_groupe"))
        except Exception as e:
            logger.warning(f"Erreur keyword reply: {e}")


@log_handler
def handle_media(update, context):
    """Gestion des médias (photos, vocaux, etc.) en privé."""
    chat = update.effective_chat

    if chat.type != "private":
        return

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=MEDIA_RESPONSE,
        )
    except Exception as e:
        logger.warning(f"Erreur réponse média: {e}")


@log_handler
def private_ai_chat(update, context):
    """Chat IA en privé avec historique de conversation."""
    message = update.message
    chat = message.chat
    user = message.from_user

    user_text = (message.text or "").strip()
    if not user_text:
        return

    stats["total_private_messages"] += 1

    # Rate limiting
    if is_rate_limited(user.id):
        logger.warning(f"⚠️ Rate limit atteint pour user {user.id}")
        try:
            message.reply_text(RATE_LIMIT_MSG)
        except Exception:
            pass
        return

    # Typing indicator
    send_typing(context, chat.id)

    # Pas de clé OpenAI → fallback
    if not OPENAI_API_KEY:
        logger.info("Pas de clé OpenAI, fallback")
        try:
            message.reply_text(
                "Je ne peux pas utiliser l'IA pour l'instant, "
                "mais découvre Mad2Moi ici : https://www.mad2moi.com/"
            )
        except Exception as e:
            logger.warning(f"Erreur fallback: {e}")
        return

    # Construire l'historique de conversation
    user_conversations[user.id].append({"role": "user", "content": user_text})

    # Garder seulement les N derniers messages
    if len(user_conversations[user.id]) > MAX_HISTORY * 2:
        user_conversations[user.id] = user_conversations[user.id][-MAX_HISTORY * 2:]

    # Préparer les messages pour OpenAI
    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
    messages.extend(user_conversations[user.id])

    # Appel OpenAI
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
            presence_penalty=0.3,
            frequency_penalty=0.3,
        )
        answer = completion.choices[0].message["content"].strip()
        stats["total_ai_responses"] += 1

        # Sauvegarder la réponse dans l'historique
        user_conversations[user.id].append({"role": "assistant", "content": answer})

        logger.info(f"✅ Réponse IA ({len(answer)} chars) - Total: {stats['total_ai_responses']}")

    except openai.error.RateLimitError:
        logger.error("❌ OpenAI rate limit atteint")
        answer = (
            "Je suis un peu débordée en ce moment 😅\n\n"
            "En attendant, découvre Mad2Moi : https://www.mad2moi.com/"
        )
    except openai.error.APIError as e:
        logger.error(f"❌ OpenAI API error: {e}")
        answer = (
            "Un petit souci technique de mon côté…\n\n"
            "Tu peux déjà t'inscrire sur Mad2Moi : https://www.mad2moi.com/"
        )
    except Exception as e:
        logger.error(f"❌ Erreur OpenAI inattendue: {e}")
        answer = (
            "Je n'arrive pas à répondre pour le moment.\n\n"
            "Découvre Mad2Moi ici : https://www.mad2moi.com/"
        )

    # Envoyer la réponse
    try:
        message.reply_text(answer)
    except Exception as e:
        logger.warning(f"Erreur envoi réponse: {e}")


@log_handler
def cmd_stats(update, context):
    """/stats : stats internes (admin only)."""
    user = update.effective_user
    chat = update.effective_chat

    # Liste des admin IDs (à configurer)
    admin_ids_str = os.environ.get("ADMIN_IDS", "")
    ADMIN_IDS = [int(x) for x in admin_ids_str.split(",") if x.strip()]

    if user.id not in ADMIN_IDS:
        return

    stats_text = f"""📊 **Stats Mad2Moi Bot**

👥 Nouveaux membres: {stats['total_new_members']}
💬 Messages privés: {stats['total_private_messages']}
🤖 Réponses IA: {stats['total_ai_responses']}
👆 Clics boutons: {dict(stats['button_clicks'])}

🧠 Users en mémoire: {len(user_conversations)}
⏱️ Rate limit actifs: {len(user_last_messages)}"""

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

    # 1. Événements groupe
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

    # 4. Auto-réponse groupe (keywords)
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.chat_type.groups,
        keyword_auto_reply
    ))

    # 5. Médias en privé (photos, vocaux, etc.)
    dp.add_handler(MessageHandler(
        (Filters.photo | Filters.voice | Filters.video | Filters.document)
        & Filters.chat_type.private,
        handle_media
    ))

    # 6. IA en privé (texte)
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.chat_type.private,
        private_ai_chat
    ))

    logger.info("=" * 50)
    logger.info("🚀 Mad2Moi Bot démarré")
    logger.info(f"   OpenAI: {'✅' if OPENAI_API_KEY else '❌'}")
    logger.info(f"   Rate limit: {RATE_LIMIT_MESSAGES} msg/{RATE_LIMIT_WINDOW}s")
    logger.info(f"   Historique IA: {MAX_HISTORY} messages")
    logger.info("=" * 50)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
