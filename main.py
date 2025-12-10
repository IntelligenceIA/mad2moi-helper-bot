import os
import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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

# --- CONFIG / LOGS ---

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 🔐 Tokens / clés
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# OpenAI : on lit la clé de manière SÉCURISÉE (pas de crash si absente)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY non défini — l'IA sera désactivée.")
else:
    openai.api_key = OPENAI_API_KEY
    logger.info("OPENAI_API_KEY chargée avec succès.")

# URL de base Mad2Moi
M2M_BASE_URL = "https://www.mad2moi.com/"

# Groupe Facebook Mad2Moi
FB_MAD2MOI_URL = "https://www.facebook.com/groups/1095227448813415/?ref=share"

# Campagne UTM principale pour ce groupe
M2M_CAMPAIGN = "non_vax_groupe"

# Persona IA
AI_SYSTEM_PROMPT = (
    "Tu es une conseillère bienveillante et directe pour la communauté Mad2Moi, "
    "un site de rencontres et de liens entre personnes libres, éveillées, souvent critiques "
    "envers le système. Ton rôle :\n"
    "- écouter la personne, comprendre ce qu'elle vit (solitude, décalage, rejet, manque de vrais liens) ;\n"
    "- lui donner des conseils simples, concrets, applicables sur la vie sociale, amoureuse et amicale ;\n"
    "- la rassurer sur le fait qu'elle n'est pas seule et qu'il existe une communauté alignée avec ses valeurs ;\n"
    "- l'orienter régulièrement vers l'inscription sur Mad2Moi.\n\n"
    "RÈGLES IMPORTANTES :\n"
    "- Ton ton est chaleureux, humain, franc, sans langue de bois, mais toujours respectueux.\n"
    "- Tu ne donnes PAS de conseils médicaux, financiers ou juridiques.\n"
    "- Tu évites tout contenu sexuel explicite, tu restes soft, suggéré, centré sur les émotions et les valeurs.\n"
    "- Tu ne promets jamais de miracle, tu parles de possibilités, d'opportunités, de rencontres probables.\n"
    "- Tu rappelles régulièrement, avec des formulations variées, que Mad2Moi est l'endroit idéal pour rencontrer "
    "des personnes qui pensent comme eux (libres, éveillées, respectueuses).\n"
    "- Tu rediriges vers Mad2Moi dès que : la personne parle de solitude, de rencontres, de décalage avec les autres, "
    "de besoin d'amis, de besoin d'amour, de cercle social aligné.\n"
    "- Tu restes brève : 5 à 10 lignes maximum par réponse, structurées, faciles à lire.\n\n"
    "CALL TO ACTION :\n"
    "Tu termines la plupart de tes réponses (au moins 2 messages sur 3) par une phrase de ce type (tu peux varier la forme) :\n"
    "- 'Si tu veux passer du virtuel au réel, le mieux est de t'inscrire sur Mad2Moi : https://www.mad2moi.com/'\n"
    "- 'Tu peux déjà créer ton profil sur Mad2Moi, c'est là que tu trouveras vraiment des gens comme toi : https://www.mad2moi.com/'\n"
    "- 'Honnêtement, le plus simple pour rencontrer des personnes alignées, c'est Mad2Moi : https://www.mad2moi.com/'\n"
    "Tu restes toujours encourageante : ton but est que la personne se sente comprise, reboostée, et qu'elle voie "
    "Mad2Moi comme la suite logique de la conversation."
)

# --- UTILITAIRES LIENS / BOUTONS ---


def make_m2m_url(step: str = "") -> str:
    url = (
        f"{M2M_BASE_URL}"
        f"?utm_source=telegram"
        f"&utm_medium=bot"
        f"&utm_campaign={M2M_CAMPAIGN}"
    )
    if step:
        url += f"&utm_content={step}"
    return url


def m2m_keyboard(step: str) -> InlineKeyboardMarkup:
    btn_m2m = InlineKeyboardButton(
        "➡ Rejoindre Mad2Moi",
        url=make_m2m_url(step),
    )
    btn_fb = InlineKeyboardButton(
        "📣 Groupe Facebook Mad2Moi",
        url=FB_MAD2MOI_URL,
    )
    return InlineKeyboardMarkup([[btn_m2m], [btn_fb]])


WELCOME_PUBLIC = (
    "👋 Bienvenue parmi nous !\n\n"
    "Ici, tu es dans un groupe 100 % bienveillant, réservé aux personnes "
    "qui veulent rencontrer des gens libres, éveillés et non-injectés.\n\n"
    "🔥 Pour faire de vraies rencontres, la plateforme officielle :\n"
    "👉 Mad2Moi (bouton ci-dessous)\n\n"
    "📩 Pour recevoir un message privé avec tous les liens utiles, "
    "clique sur le bot @mad2moi_helper_bot et appuie sur /start.\n\n"
    "Présente-toi quand tu veux : prénom, région, ce que tu cherches.\n"
    "Encore bienvenue ✨ Tu es chez toi ici."
)

WELCOME_DM = (
    "👋 Bienvenue dans le groupe des libres non-vax !\n\n"
    "Ici, tu vas pouvoir rencontrer des personnes qui pensent comme toi : "
    "authentiques, éveillées, bienveillantes et surtout… sans censure.\n\n"
    "🔥 Pour faire de vraies rencontres (amicales ou amoureuses), "
    "clique sur le bouton ci-dessous pour rejoindre la plateforme officielle : Mad2Moi.\n\n"
    "C'est gratuit à l'inscription, sécurisé, et réservé à des gens qui partagent nos valeurs.\n\n"
    "Si tu veux, tu peux déjà me dire ta région et ce que tu recherches : "
    "amitié, rencontres, discussions… Je t'aide à t'orienter."
)

HELP_TEXT = (
    "👋 Je suis le bot Mad2Moi.\n\n"
    "▶ Quand tu rejoins le groupe, tu peux me lancer en privé avec /start :\n"
    " • je t'explique comment fonctionne Mad2Moi\n"
    " • je t'envoie les bons liens\n"
    " • je te propose un menu (rencontres / amitié / découverte)\n\n"
    "Tu peux aussi simplement m'écrire en privé : je te répondrai avec l'IA Mad2Moi.\n\n"
    "🔥 Pour découvrir la plateforme : clique sur le bouton ci-dessous."
)

FOLLOWUP_TEXT = (
    "👋 Re-bonjour, c'est le bot Mad2Moi.\n\n"
    "Tu as eu le temps de découvrir la plateforme Mad2Moi ? "
    "C'est là que les membres du groupe font de vraies rencontres "
    "(amicales, amoureuses, projets…).\n\n"
    "Tu peux t'inscrire ici, c'est rapide et sécurisé :"
)

KEYWORDS_RENCONTRE = [
    "rencontrer",
    "rencontre",
    "célibataire",
    "copine",
    "copain",
    "je cherche une fille",
    "je cherche un mec",
    "j'ai envie de rencontrer",
]


# --- HANDLERS TELEGRAM ---


def welcome_new_members(update: Update, context: CallbackContext) -> None:
    """Message PUBLIC quand quelqu'un rejoint le groupe."""
    message = update.message
    chat = message.chat
    keyboard_public = m2m_keyboard("welcome_public")

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue

        logger.info(f"Nouveau membre : {new_member.first_name} (ID: {new_member.id})")

        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=WELCOME_PUBLIC,
                reply_markup=keyboard_public,
            )
        except Exception as e:
            logger.warning(f"Erreur envoi message groupe : {e}")


def followup_job(context: CallbackContext) -> None:
    """DM automatique 24h après /start."""
    user_id = context.job.context
    keyboard = m2m_keyboard("followup")
    try:
        context.bot.send_message(
            chat_id=user_id,
            text=FOLLOWUP_TEXT,
            reply_markup=keyboard,
        )
        logger.info(f"Follow-up envoyé à {user_id}")
    except Exception as e:
        logger.warning(f"Erreur envoi follow-up : {e}")


def start_or_help(update: Update, context: CallbackContext) -> None:
    """
    /start et /help :
    - en groupe : renvoie vers le privé
    - en privé : envoie WELCOME_DM + menu + relance 24h
    """
    chat = update.effective_chat
    user = update.effective_user

    logger.info(f"/start ou /help reçu de {user.first_name} (ID: {user.id}, chat_type: {chat.type})")

    # /start dans un GROUPE → on donne juste le lien vers le privé
    if chat.type in ("group", "supergroup"):
        private_link = "https://t.me/mad2moi_helper_bot?start=go"
        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "📩 Pour discuter avec moi en privé et recevoir tous les liens "
                    "Mad2Moi, clique ici :\n"
                    f"{private_link}"
                ),
            )
        except Exception as e:
            logger.warning(f"Erreur envoi /start dans groupe : {e}")
        return

    # /start en PRIVÉ → tunnel DM
    keyboard = m2m_keyboard("welcome_dm")

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=WELCOME_DM,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"Erreur envoi WELCOME_DM : {e}")

    menu_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💘 Je cherche des rencontres",
                    callback_data="menu_rencontres",
                )
            ],
            [
                InlineKeyboardButton(
                    "🤝 Je veux lier amitié",
                    callback_data="menu_amitie",
                )
            ],
            [
                InlineKeyboardButton(
                    "👀 Je découvre le groupe",
                    callback_data="menu_decouverte",
                )
            ],
        ]
    )

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text="Dis-moi ce que tu cherches, je te guide 👇",
            reply_markup=menu_keyboard,
        )
    except Exception as e:
        logger.warning(f"Erreur envoi menu DM /start : {e}")

    try:
        context.job_queue.run_once(
            followup_job,
            when=24 * 60 * 60,
            context=chat.id,
            name=f"followup_{user.id}",
        )
    except Exception as e:
        logger.warning(f"Erreur programmation follow-up : {e}")


def menu_callback(update: Update, context: CallbackContext) -> None:
    """Réponses aux boutons du menu en DM."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    logger.info(f"Callback menu reçu : {data} de user {user_id}")

    query.answer()

    if data == "menu_rencontres":
        txt = (
            "💘 Parfait. Pour les rencontres (amicales ou amoureuses), "
            "le plus simple est de t'inscrire sur Mad2Moi : tu y trouveras "
            "des personnes qui pensent comme toi, sans censure.\n\n"
            "Clique sur le bouton ci-dessous pour t'inscrire :"
        )
        step = "menu_rencontres"

    elif data == "menu_amitie":
        txt = (
            "🤝 Tu veux surtout élargir ton cercle d'amis éveillés, c'est top.\n\n"
            "Mad2Moi permet aussi de créer des liens amicaux locaux ou à distance. "
            "Inscris-toi ici pour trouver des profils qui partagent ta vision :"
        )
        step = "menu_amitie"

    else:
        txt = (
            "👀 Tu peux prendre le temps de découvrir…\n\n"
            "Quand tu seras prêt(e), crée ton profil sur Mad2Moi : "
            "tu restes maître de ce que tu partages et tu rencontres des gens "
            "qui respectent tes choix.\n\n"
            "Le bouton ci-dessous te permet de t'inscrire :"
        )
        step = "menu_decouverte"

    keyboard = m2m_keyboard(step)

    try:
        context.bot.send_message(chat_id=user_id, text=txt, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Erreur envoi réponse menu : {e}")


def keyword_auto_reply(update: Update, context: CallbackContext) -> None:
    """
    Répond automatiquement dans le GROUPE quand quelqu'un parle de rencontres.
    Note : ce handler n'est appelé QUE pour les groupes grâce au filtre.
    """
    message = update.message
    user = message.from_user

    if user.is_bot:
        return

    text = (message.text or "").lower()

    if any(k in text for k in KEYWORDS_RENCONTRE):
        logger.info(f"Keyword détecté dans groupe : '{text[:50]}...' de {user.first_name}")
        keyboard = m2m_keyboard("keyword_rencontres")
        reply = (
            "💡 Petit rappel : pour faire de vraies rencontres avec des personnes "
            "non-vax / éveillées, le plus simple est de passer par Mad2Moi.\n\n"
            "Tu peux t'inscrire ici :"
        )
        try:
            message.reply_text(reply, reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"Erreur envoi auto-reply : {e}")


# --- IA OPENAI EN PRIVÉ ---


def private_ai_chat(update: Update, context: CallbackContext) -> None:
    """
    Chat IA en PRIVÉ :
    - si quelqu'un écrit en DM au bot (hors commandes), on envoie à OpenAI
    - si pas de clé OPENAI_API_KEY → réponse fallback, pas de crash
    """
    message = update.message
    chat = message.chat
    user = message.from_user

    user_text = (message.text or "").strip()
    if not user_text:
        return

    logger.info(f"[PRIVÉ] Message reçu de {user.first_name} (ID: {user.id}): '{user_text[:50]}...'")

    # Pas de clé → pas d'appel OpenAI, on répond juste avec un message fixe
    if not OPENAI_API_KEY:
        logger.info("Pas de clé OpenAI, envoi réponse fallback.")
        try:
            message.reply_text(
                "Pour l'instant, je ne peux pas utiliser l'IA, "
                "mais tu peux déjà découvrir Mad2Moi ici : https://www.mad2moi.com/"
            )
        except Exception as e:
            logger.warning(f"Erreur envoi réponse fallback IA : {e}")
        return

    # Appel OpenAI
    logger.info("Appel OpenAI en cours...")
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.6,
            max_tokens=400,
        )
        answer = completion.choices[0].message["content"].strip()
        logger.info(f"Réponse OpenAI reçue ({len(answer)} chars)")
    except Exception as e:
        logger.error(f"Erreur appel OpenAI : {e}")
        answer = (
            "Je n'arrive pas à répondre avec l'IA pour le moment. "
            "Mais tu peux déjà découvrir Mad2Moi ici : https://www.mad2moi.com/"
        )

    try:
        message.reply_text(answer)
        logger.info(f"Réponse envoyée à {user.first_name}")
    except Exception as e:
        logger.warning(f"Erreur envoi réponse IA : {e}")


# --- MAIN ---


def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # 1. Nouveaux membres : message de bienvenue PUBLIC
    dp.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, welcome_new_members)
    )

    # 2. Commandes /start et /help (priorité avant les messages texte)
    dp.add_handler(CommandHandler("start", start_or_help))
    dp.add_handler(CommandHandler("help", start_or_help))

    # 3. Auto-réponse sur mots-clés UNIQUEMENT dans les GROUPES
    #    ⚠️ CORRECTION : ajout de Filters.chat_type.groups
    dp.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command & Filters.chat_type.groups,
            keyword_auto_reply,
        )
    )

    # 4. Boutons du menu en DM
    dp.add_handler(CallbackQueryHandler(menu_callback))

    # 5. IA en privé (tous les messages texte privés hors commandes)
    dp.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command & Filters.chat_type.private,
            private_ai_chat,
        )
    )

    logger.info("=== Mad2Moi helper bot démarré ===")
    logger.info(f"OpenAI actif : {bool(OPENAI_API_KEY)}")

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
