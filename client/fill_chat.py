#!/usr/bin/env python3
"""
Скрипт для наполнения чата случайными сообщениями.

Использование:
    python3 fill_chat.py <chat_id> <nickname> [--count N] [--server ADDRESS]

Примеры:
    python3 fill_chat.py my_chat user1
    python3 fill_chat.py my_chat user1 --count 100
    python3 fill_chat.py my_chat user1 --count 50 --server localhost:8080
"""

import argparse
import random
import time
import sys
import grpc
from generated import messenger_pb2
from generated import messenger_pb2_grpc


# Примеры сообщений для генерации
MESSAGE_TEMPLATES = [
    "Привет! Как дела?",
    "Сегодня отличная погода!",
    "Что планируешь на выходные?",
    "Посмотрел новый фильм, очень понравилось",
    "Работаю над интересным проектом",
    "У кого-нибудь есть идеи для улучшения?",
    "Спасибо за помощь!",
    "Отличная работа, команда!",
    "Нужно обсудить детали",
    "Когда будет следующая встреча?",
    "Проверьте, пожалуйста, мой код",
    "Есть вопросы по задаче",
    "Готов к ревью",
    "Все работает отлично",
    "Нужна помощь с деплоем",
    "Обновил документацию",
    "Исправил баг",
    "Добавил новую функцию",
    "Тесты проходят успешно",
    "Нужно обновить зависимости",
]

TAGS = [
    "важно",
    "срочно",
    "вопрос",
    "помощь",
    "идея",
    "обсуждение",
    "код",
    "баг",
    "фича",
    "документация",
]


def generate_random_message():
    """Генерирует случайное сообщение с возможными тегами"""
    message = random.choice(MESSAGE_TEMPLATES)
    
    # С вероятностью 30% добавляем теги
    if random.random() < 0.3:
        num_tags = random.randint(1, 3)
        selected_tags = random.sample(TAGS, min(num_tags, len(TAGS)))
        tags_str = " ".join([f"#{tag}" for tag in selected_tags])
        message = f"{message} {tags_str}"
    
    # С вероятностью 20% добавляем случайные числа или символы
    if random.random() < 0.2:
        message = f"{message} {random.randint(1, 1000)}"
    
    return message


def send_message(stub, chat_id, nickname, content):
    """Отправляет сообщение в чат"""
    try:
        request = messenger_pb2.SendMessageRequest(
            message=content,
            chat_id=chat_id,
            nickname=nickname
        )
        response = stub.SendMessage(request)
        return response.message_id
    except grpc.RpcError as e:
        print(f"❌ Ошибка отправки сообщения: {e}", file=sys.stderr)
        return None


def fill_chat(server_address, chat_id, nickname, count=50, delay=0.1):
    """Наполняет чат случайными сообщениями"""
    print(f"🔗 Подключение к серверу {server_address}...")
    
    try:
        channel = grpc.insecure_channel(server_address)
        stub = messenger_pb2_grpc.MessengerStub(channel)
        
        # Проверяем подключение
        try:
            grpc.channel_ready_future(channel).result(timeout=5)
            print(f"✅ Подключено к серверу")
        except grpc.FutureTimeoutError:
            print(f"❌ Не удалось подключиться к серверу за 5 секунд", file=sys.stderr)
            channel.close()
            return False
        
        print(f"📝 Начинаю отправку {count} сообщений в чат '{chat_id}' от пользователя '{nickname}'...")
        print(f"⏱️  Задержка между сообщениями: {delay} секунд")
        print("-" * 60)
        
        successful = 0
        failed = 0
        
        for i in range(count):
            message = generate_random_message()
            message_id = send_message(stub, chat_id, nickname, message)
            
            if message_id:
                successful += 1
                print(f"[{i+1}/{count}] ✅ Отправлено: {message[:50]}...")
            else:
                failed += 1
                print(f"[{i+1}/{count}] ❌ Не удалось отправить сообщение")
            
            # Задержка между сообщениями
            if i < count - 1:
                time.sleep(delay)
        
        channel.close()
        
        print("-" * 60)
        print(f"✅ Готово! Успешно отправлено: {successful}, Ошибок: {failed}")
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Наполняет чат случайными сообщениями',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'chat_id',
        help='ID чата для наполнения'
    )
    
    parser.add_argument(
        'nickname',
        help='Никнейм отправителя сообщений'
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=50,
        help='Количество сообщений для отправки (по умолчанию: 50)'
    )
    
    parser.add_argument(
        '--server',
        default='localhost:8080',
        help='Адрес gRPC сервера (по умолчанию: localhost:8080)'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=0.1,
        help='Задержка между сообщениями в секундах (по умолчанию: 0.1)'
    )
    
    args = parser.parse_args()
    
    if args.count <= 0:
        print("❌ Количество сообщений должно быть положительным числом", file=sys.stderr)
        sys.exit(1)
    
    if args.delay < 0:
        print("❌ Задержка не может быть отрицательной", file=sys.stderr)
        sys.exit(1)
    
    success = fill_chat(
        server_address=args.server,
        chat_id=args.chat_id,
        nickname=args.nickname,
        count=args.count,
        delay=args.delay
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

