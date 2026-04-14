#!/bin/bash
# Radiance Bot — автодеплой на Timeweb
set -e

echo "🔧 Fixing DNS..."
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

echo "📦 Stopping old bot if running..."
pm2 delete radiance-bot 2>/dev/null || true

echo "📁 Backing up database..."
cp /root/radiance/shop.db /tmp/shop.db.bak 2>/dev/null || true

echo "📁 Cleaning old files..."
rm -rf /root/radiance

echo "⬇️ Cloning repo..."
git clone https://github.com/mmo-rgb/telegram.bot.git /root/radiance

echo "📁 Restoring database..."
cp /tmp/shop.db.bak /root/radiance/shop.db 2>/dev/null || true

echo "🐍 Creating venv..."
cd /root/radiance
python3 -m venv venv
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🚀 Starting bot with PM2..."
pm2 start venv/bin/python --name "radiance-bot" -- bot.py
pm2 save
pm2 startup 2>/dev/null || true

echo ""
echo "✅ Готово! Бот запущен."
echo "📊 Статус: pm2 status"
echo "📋 Логи:   pm2 logs radiance-bot"
