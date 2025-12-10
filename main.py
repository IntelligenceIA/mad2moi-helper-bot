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

# 🔐 Tokens / clés
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
openai.api_key = os.environ["OPENAI_API_KEY"]

# URL de base Mad2Moi
M2M_BASE_URL = "https://www.mad2moi.com/"

# Groupe Facebook Mad2Moi (officiel)
FB_MAD2MOI_URL = "https://www.facebook.com/groups/1095227448813415/?ref=share"

# Campagne UTM principale pour ce groupe
M2M_CAMPAIGN = "non_vax_groupe"

# Persona IA : coach Mad2Moi
AI_SYSTEM_PROMPT = (
    "Tu es une conseillère bienveillante pour la communauté Mad2Moi, un site de "
    "rencontres et de liens entre personnes libres, éveillées, souvent non-vax. "
    "Ta mission : écouter, rassurer, donner des conseils relationnels, émotionnels, "
    "sociaux, et ORIENTER subtilement mais fermement vers l'inscription sur Mad2Moi.\n\n"
    "Règles :\n"
    "- Ton ton est chaleureux, direct, honnête, pas mielleux.\n"
    "- Tu ne donnes PAS de conseils médicaux ni financiers.\n"
    "- Tu restes soft : pas de porno, pas de détail sexuel cru.\n"
    "- Tu rappelles régulièrement que Mad2Moi est l'endroit idéal pour rencontrer "
    "des personnes qui partagent leurs valeurs.\n"
    "- Tu termines la plupart de tes réponses par un call-to-action discret vers Mad2Moi, "
    "avec cette phrase (ou variante proche) :\n"
    "  'Si tu veux passer du virtuel au réel avec des gens comme toi, le mieux est de t'inscrire sur Mad2Moi : https://www.mad2moi.com/'\n"
)

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
    "C’est gratuit à l’inscription, sécurisé, et réservé à des gens qui partagent nos valeurs.\n\n"
    "Si tu veux, tu peux déjà me dire ta région et ce que tu recherches : "
    "amitié, rencontres, discussions… Je t’aide à t’orienter."
)

HELP_TEXT = (
    "👋 Je suis le bot Mad2Moi.\n\n"
    "▶ Quand tu rejoins le groupe, tu peux me lancer en privé avec /start :\n"
    " • je t’explique comment fonctionne Mad2Moi\n"
    " • je t’envoie les bons liens\n"
    " • je te propose un menu (rencontres / amitié / découverte)\n\n"
    "Tu peux aussi simplement m'écrire en privé : je te répondrai avec l'IA Mad2Moi.\n\n"
    "🔥 Pour découvrir la plateforme : clique sur le bouton ci-dessous."
)

FOLLOWUP_TEXT = (
    "👋 Re-bonjour, c’est le bot Mad2Moi.\n\n"
    "Tu as eu le temps de découvrir la plateforme Mad2Moi ? "
    "C’est là que les membres du groupe font de vraies rencontres "
    "(amicales, amoureuses, projets…).\n\n"
    "Tu peux t’inscrire ici, c’est rapide et sécurisé :"
)

KEYWORDS_RENCONTRE = [
    "rencontrer",
    "rencontre",
    "célibataire",
    "copine",
    "copain",
    "je cherche une fille",
    "je cherche un mec",
    "j’ai envie de rencontrer",
]


# --- HANDLERS TELEGRAM ---


def welcome_new_members(update: Update, context: CallbackContext) -> None:
    message = update.message
    chat = message.chat
    keyboard_public = m2m_keyboard("welcome_public")

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue

        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=WELCOME_PUBLIC,
                reply_markup=keyboard_public,
            )
        except Exception as e:
            logging.warning(f"Erreur envoi message groupe : {e}")


def followup_job(context: CallbackContext) -> None:
    user_id = context.job.context
    keyboard = m2m_keyboard("followup")
    try:
        context.bot.send_message(
            chat_id=user_id,
            text=FOLLOWUP_TEXT,
            reply_markup=keyboard,
        )
    except Exception as e:
        logging.warning(f"Erreur envoi follow-up : {e}")


def start_or_help(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    user = update.effective_user

    # /start dans un groupe → on renvoie vers le privé
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
            logging.warning(f"Erreur envoi /start dans groupe : {e}")
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
        logging.warning(f"Erreur envoi WELCOME_DM : {e}")

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
        logging.warning(f"Erreur envoi menu DM /start : {e}")

    try:
        context.job_queue.run_once(
            followup_job,
            when=24 * 60 * 60,
            context=chat.id,
            name=f"followup_{user.id}",
        )
    except Exception as e:
        logging.warning(f"Erreur programmation follow-up : {e}")


def menu_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    query.answer()

    if data == "menu_rencontres":
        txt = (
            "💘 Parfait. Pour les rencontres (amicales ou amoureuses), "
            "le plus simple est de t’inscrire sur Mad2Moi : tu y trouveras "
            "des personnes qui pensent comme toi, sans censure.\n\n"
            "Clique sur le bouton ci-dessous pour t’inscrire :"
        )
        step = "menu_rencontres"

    elif data == "menu_amitie":
        txt = (
            "🤝 Tu veux surtout élargir ton cercle d'amis éveillés, c’est top.\n\n"
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
            "Le bouton ci-dessous te permet de t’inscrire :"
        )
        step = "menu_decouverte"

    keyboard = m2m_keyboard(step)

    try:
        context.bot.send_message(chat_id=user_id, text=txt, reply_markup=keyboard)
    except Exception as e:
        logging.warning(f"Erreur envoi réponse menu : {e}")


def keyword_auto_reply(update: Update, context: CallbackContext) -> None:
    """
    Répond automatiquement dans le GROUPE quand quelqu’un parle de rencontres.
    (On ne le déclenche pas en privé.)
    """
    message = update.message
    user = message.from_user
    chat = message.chat

    if chat.type not in ("group", "supergroup"):
        return

    text = (message.text or "").lower()
    if user.is_bot:
        return

    if any(k in text for k in KEYWORDS_RENCONTRE):
        keyboard = m2m_keyboard("keyword_rencontres")
        reply = (
            "💡 Petit rappel : pour faire de vraies rencontres avec des personnes "
            "non-vax / éveillées, le plus simple est de passer par Mad2Moi.\n\n"
            "Tu peux t’inscrire ici :"
        )
        try:
            message.reply_text(reply, reply_markup=keyboard)
        except Exception as e:
            logging.warning(f"Erreur envoi auto-reply : {e}")


# --- IA OPENAI EN PRIVÉ ---


def private_ai_chat(update: Update, context: CallbackContext) -> None:
    """
    Chat IA en PRIVÉ :
    - si quelqu’un écrit en DM au bot (hors commandes), on envoie à OpenAI
    - et on répond en gardant la logique de conversion Mad2Moi
    """
    message = update.message
    chat = message.chat

    # On ne gère ici que les DM privés, pas les groupes
    if chat.type != "private":
        return

    user_text = (message.text or "").strip()
    if not user_text:
        return

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
    except Exception as e:
        logging.error(f"Erreur appel OpenAI : {e}")
        answer = (
            "Je n'arrive pas à répondre avec l'IA pour le moment. "
            "Mais tu peux déjà découvrir Mad2Moi ici : https://www.mad2moi.com/"
        )

    try:
        message.reply_text(answer)
    except Exception as e:
        logging.warning(f"Erreur envoi réponse IA : {e}")


# --- MAIN ---


def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Nouveaux membres / message de bienvenue PUBLIC
    dp.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, welcome_new_members)
    )

    # Auto-réponse sur mots-clés dans le groupe
    dp.add_handler(
        MessageHandler(Filters.text & ~Filters.command, keyword_auto_reply)
    )

    # Commandes /start et /help
    dp.add_handler(CommandHandler("start", start_or_help))
    dp.add_handler(CommandHandler("help", start_or_help))

    # Boutons du menu en DM
    dp.add_handler(CallbackQueryHandler(menu_callback))

    # IA en privé (tous les messages texte privés hors commandes)
    dp.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command & Filters.chat_type.private,
            private_ai_chat,
        )
    )

    logging.info("Mad2Moi helper bot démarré (full options + IA OpenAI).")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
