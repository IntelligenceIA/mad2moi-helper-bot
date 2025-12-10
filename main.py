import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater,
    MessageHandler,
    Filters,
    CallbackContext,
    CommandHandler,
)

# Logs utiles sur Railway
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# 🔐 Token récupéré dans les variables Railway (TELEGRAM_TOKEN)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# 🔗 Lien traqué vers Mad2Moi (UTM pour savoir d'où viennent les inscrits)
M2M_URL = (
    "https://www.mad2moi.com/"
    "?utm_source=telegram"
    "&utm_medium=bot"
    "&utm_campaign=non_vax_groupe"
)

WELCOME_PUBLIC = (
    "👋 Bienvenue parmi nous !\n\n"
    "Ici, tu es dans un groupe 100 % bienveillant, réservé aux personnes "
    "qui veulent rencontrer des gens libres, éveillés et non-injectés.\n\n"
    "🔥 Pour faire de vraies rencontres, la plateforme officielle :\n"
    "👉 Mad2Moi (bouton ci-dessous)\n\n"
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
    "▶ Quand tu rejoins le groupe, je t’envoie :\n"
    " • un message d’accueil dans le groupe\n"
    " • un message privé avec le lien vers Mad2Moi\n\n"
    "🔥 Pour découvrir la plateforme : clique sur le bouton ci-dessous."
)


def get_m2m_keyboard() -> InlineKeyboardMarkup:
    """Clavier avec le bouton Mad2Moi."""
    button = InlineKeyboardButton("➡ Rejoindre Mad2Moi", url=M2M_URL)
    keyboard = InlineKeyboardMarkup([[button]])
    return keyboard


def welcome_new_members(update: Update, context: CallbackContext) -> None:
    """Appelé automatiquement quand quelqu'un rejoint le groupe."""
    message = update.message
    chat = message.chat
    keyboard = get_m2m_keyboard()

    for new_member in message.new_chat_members:
        # 1) message public dans le groupe
        try:
            context.bot.send_message(
                chat_id=chat.id,
                text=WELCOME_PUBLIC,
                reply_markup=keyboard,
            )
        except Exception as e:
            logging.warning(f"Erreur envoi message groupe : {e}")

        # 2) message privé (DM)
        try:
            context.bot.send_message(
                chat_id=new_member.id,
                text=WELCOME_DM,
                reply_markup=keyboard,
            )
        except Exception as e:
            # Souvent: l'utilisateur bloque les DM de bots → ce n'est pas grave
            logging.warning(f"Erreur envoi DM : {e}")


def start_or_help(update: Update, context: CallbackContext) -> None:
    """Répond à /start et /help, surtout en privé."""
    chat = update.effective_chat
    keyboard = get_m2m_keyboard()

    try:
        context.bot.send_message(
            chat_id=chat.id,
            text=HELP_TEXT,
            reply_markup=keyboard,
        )
    except Exception as e:
        logging.warning(f"Erreur envoi /start ou /help : {e}")


def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Quand quelqu'un rejoint le groupe
    dp.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, welcome_new_members)
    )

    # Commandes /start et /help
    dp.add_handler(CommandHandler("start", start_or_help))
    dp.add_handler(CommandHandler("help", start_or_help))

    logging.info("Mad2Moi helper bot démarré avec CTA + /start + /help.")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
