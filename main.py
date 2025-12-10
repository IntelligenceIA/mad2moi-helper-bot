import os
import logging
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

WELCOME_PUBLIC = (
    "👋 Bienvenue parmi nous !\n\n"
    "Ici, tu es dans un groupe 100 % bienveillant, réservé aux personnes "
    "qui veulent rencontrer des gens libres, éveillés et non-injectés.\n\n"
    "🔥 Pour faire de vraies rencontres, la plateforme officielle :\n"
    "👉 https://www.mad2moi.com\n\n"
    "Présente-toi quand tu veux : prénom, région, ce que tu cherches.\n"
    "Encore bienvenue ✨ Tu es chez toi ici."
)

WELCOME_DM = (
    "👋 Bienvenue dans le groupe des libres non-vax !\n\n"
    "Ici, tu vas pouvoir rencontrer des personnes qui pensent comme toi : "
    "authentiques, éveillées, bienveillantes et surtout… sans censure.\n\n"
    "🔥 Si tu veux faire de vraies rencontres (amicales ou amoureuses), "
    "la plateforme officielle de notre communauté est ici :\n"
    "👉 https://www.mad2moi.com\n\n"
    "C’est gratuit à l’inscription, sécurisé, et réservé à des gens qui partagent nos valeurs.\n\n"
    "Si tu veux, tu peux déjà me dire ta région et ce que tu recherches : "
    "amitié, rencontres, discussions… Je t’aide à t’orienter."
)


def welcome_new_members(update: Update, context: CallbackContext) -> None:
    message = update.message
    chat = message.chat

    for new_member in message.new_chat_members:
        # 1) message public dans le groupe
        try:
            context.bot.send_message(chat_id=chat.id, text=WELCOME_PUBLIC)
        except Exception as e:
            logging.warning(f"Erreur envoi message groupe : {e}")

        # 2) message privé (DM)
        try:
            context.bot.send_message(chat_id=new_member.id, text=WELCOME_DM)
        except Exception as e:
            # si l'utilisateur bloque les DM de bots, c'est normal que ça plante
            logging.warning(f"Erreur envoi DM : {e}")


def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # déclenché quand quelqu'un rejoint le groupe
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome_new_members))

    logging.info("Mad2Moi helper bot démarré.")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
