#!/bin/sh
# Обновление бота с GitHub на Bothost
cd /app || exit 1

wget -O master.zip https://github.com/NikitaLaVida/nektarin-bot/archive/refs/heads/master.zip
unzip -o master.zip
cp -r nektarin-bot-main/* .
rm -rf nektarin-bot-main master.zip

echo "Done. Run: python gaming_news_bot.py --daemon"
