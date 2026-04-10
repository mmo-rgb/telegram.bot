"""
Автоматический запуск и обновление бота.
Каждые 30 секунд проверяет GitHub на изменения.
Если есть — делает git pull и перезапускает бота.

Использование: python auto_update.py
"""
import subprocess
import time
import sys
import os
import signal

BOT_PROCESS = None
CHECK_INTERVAL = 30  # секунд

def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS:
        BOT_PROCESS.terminate()
        BOT_PROCESS.wait()
        print("[UPDATER] Бот остановлен")
    
    print("[UPDATER] Запускаю бота...")
    BOT_PROCESS = subprocess.Popen([sys.executable, "bot.py"])
    print(f"[UPDATER] Бот запущен (PID: {BOT_PROCESS.pid})")

def check_updates():
    # Получаем последний коммит на GitHub
    subprocess.run(["git", "fetch"], capture_output=True)
    
    # Сравниваем локальный и удалённый
    local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True).stdout.strip()
    
    if local != remote:
        print("[UPDATER] Найдены обновления! Обновляю...")
        subprocess.run(["git", "pull"], capture_output=True)
        return True
    return False

def main():
    print("[UPDATER] === Авто-обновление запущено ===")
    print(f"[UPDATER] Проверка каждые {CHECK_INTERVAL} сек")
    
    # Первый запуск
    start_bot()
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            if check_updates():
                start_bot()
            else:
                # Проверяем что бот не упал
                if BOT_PROCESS and BOT_PROCESS.poll() is not None:
                    print("[UPDATER] Бот упал! Перезапускаю...")
                    start_bot()
    except KeyboardInterrupt:
        print("\n[UPDATER] Останавливаю...")
        if BOT_PROCESS:
            BOT_PROCESS.terminate()
        print("[UPDATER] Готово")

if __name__ == "__main__":
    main()
