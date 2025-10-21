#!/usr/bin/env python3
"""
Простой gRPC клиент для тестирования основных методов Messenger сервиса
"""

import grpc
import sys
import time
from generated import messenger_pb2
from generated import messenger_pb2_grpc


class MessengerClient:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None

    def connect(self):
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = messenger_pb2_grpc.MessengerStub(self.channel)
            print(f"✅ Подключен к серверу {self.server_address}")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        if self.channel:
            self.channel.close()
            print("🔌 Отключен от сервера")

    def send_message(self, message, from_nickname, to_nickname):
        try:
            request = messenger_pb2.SendMessageRequest(
                message=message,
                from_nickname=from_nickname,
                to_nickname=to_nickname
            )
            
            response = self.stub.SendMessage(request)
            print(f"📤 Сообщение отправлено! ID: {response.message_id}")
            return response.message_id
        except grpc.RpcError as e:
            print(f"❌ Ошибка отправки сообщения: {e}")
            return None

    def get_received_messages(self, nickname):
        try:
            request = messenger_pb2.GetReceivedMessagesRequest(nickname=nickname)
            response = self.stub.GetReceivedMessages(request)
            
            print(f"📥 Полученные сообщения для {nickname}:")
            if not response.messages:
                print("  (нет сообщений)")
            else:
                for msg in response.messages:
                    print(f"  📨 {msg.from_nickname} -> {msg.to_nickname}: {msg.content}")
                    print(f"      ID: {msg.id}, Время: {msg.created_at}")
            return response.messages
        except grpc.RpcError as e:
            print(f"❌ Ошибка получения сообщений: {e}")
            return []

    def get_sent_messages(self, nickname):
        try:
            request = messenger_pb2.GetSentMessagesRequest(nickname=nickname)
            response = self.stub.GetSentMessages(request)
            
            print(f"📤 Отправленные сообщения от {nickname}:")
            if not response.messages:
                print("  (нет сообщений)")
            else:
                for msg in response.messages:
                    print(f"  📨 {msg.from_nickname} -> {msg.to_nickname}: {msg.content}")
                    print(f"      ID: {msg.id}, Время: {msg.created_at}")
            return response.messages
        except grpc.RpcError as e:
            print(f"❌ Ошибка получения отправленных сообщений: {e}")
            return []


def main():
    """Основная функция для демонстрации клиента"""
    if len(sys.argv) < 2:
        print("Использование: python simple_client.py <server_address>")
        print("Пример: python simple_client.py localhost:8080")
        sys.exit(1)

    server_address = sys.argv[1]
    client = MessengerClient(server_address)

    if not client.connect():
        sys.exit(1)

    try:
        print("\n=== Тестирование gRPC Messenger клиента ===\n")

        # Тест 1: Отправка сообщений
        print("1. Отправка сообщений...")
        client.send_message("Привет, Алиса!", "Боб", "Алиса")
        client.send_message("Привет, Боб!", "Алиса", "Боб")
        client.send_message("Как дела?", "Боб", "Алиса")

        time.sleep(1)  # Небольшая пауза

        # Тест 2: Получение сообщений для Алисы
        print("\n2. Получение сообщений для Алисы...")
        client.get_received_messages("Алиса")

        # Тест 3: Получение сообщений для Боба
        print("\n3. Получение сообщений для Боба...")
        client.get_received_messages("Боб")

        # Тест 4: Получение отправленных сообщений от Алисы
        print("\n4. Отправленные сообщения от Алисы...")
        client.get_sent_messages("Алиса")

        # Тест 5: Получение отправленных сообщений от Боба
        print("\n5. Отправленные сообщения от Боба...")
        client.get_sent_messages("Боб")

        print("\n✅ Все тесты завершены!")

    except KeyboardInterrupt:
        print("\n\n⏹️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
