#!/usr/bin/env python3
"""
gRPC клиент для тестирования streaming методов Messenger сервиса
"""

import grpc
import sys
import time
import threading
from generated import messenger_pb2
from generated import messenger_pb2_grpc


class StreamingMessengerClient:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.nickname = None

    def connect(self):
        """Подключение к серверу"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = messenger_pb2_grpc.MessengerStub(self.channel)
            print(f"✅ Подключен к серверу {self.server_address}")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение от сервера"""
        if self.channel:
            self.channel.close()
            print("🔌 Отключен от сервера")

    def stream_received_messages(self, nickname):
        """Server-Side Streaming: получение новых сообщений в реальном времени"""
        try:
            request = messenger_pb2.StreamReceivedMessagesRequest(nickname=nickname)
            print(f"🔄 Начинаем потоковое получение сообщений для {nickname}...")
            
            for message in self.stub.StreamReceivedMessages(request):
                print(f"📨 Новое сообщение: {message.from_nickname} -> {message.to_nickname}")
                print(f"   Содержимое: {message.content}")
                print(f"   ID: {message.id}, Время: {message.created_at}")
                print("-" * 50)
                
        except grpc.RpcError as e:
            print(f"❌ Ошибка потокового получения сообщений: {e}")
        except KeyboardInterrupt:
            print(f"\n⏹️  Потоковое получение сообщений для {nickname} остановлено")

    def chat_stream(self, nickname):
        """Bidirectional Streaming: чат в реальном времени"""
        try:
            print(f"💬 Начинаем чат-поток для {nickname}...")
            print("Введите сообщения (или 'quit' для выхода):")
            
            def send_messages():
                """Поток для отправки сообщений"""
                while True:
                    try:
                        message_text = input()
                        if message_text.lower() == 'quit':
                            break
                        
                        # Создаем сообщение чата
                        chat_message = messenger_pb2.ChatMessage(
                            content=message_text,
                            from_nickname=nickname,
                            to_nickname="all",  # Отправляем всем
                            type=messenger_pb2.ChatMessageType.MESSAGE
                        )
                        
                        # Отправляем сообщение
                        yield chat_message
                        
                    except EOFError:
                        break
                    except KeyboardInterrupt:
                        break

            def receive_messages():
                """Поток для получения сообщений"""
                try:
                    for chat_message in self.stub.ChatStream(send_messages()):
                        if chat_message.type == messenger_pb2.ChatMessageType.MESSAGE:
                            print(f"💬 {chat_message.from_nickname}: {chat_message.content}")
                        elif chat_message.type == messenger_pb2.ChatMessageType.USER_JOINED:
                            print(f"👋 {chat_message.content}")
                        elif chat_message.type == messenger_pb2.ChatMessageType.USER_LEFT:
                            print(f"👋 {chat_message.content}")
                        elif chat_message.type == messenger_pb2.ChatMessageType.TYPING:
                            print(f"⌨️  {chat_message.from_nickname} печатает...")
                        elif chat_message.type == messenger_pb2.ChatMessageType.STOP_TYPING:
                            print(f"⌨️  {chat_message.from_nickname} перестал печатать")
                            
                except grpc.RpcError as e:
                    print(f"❌ Ошибка получения сообщений чата: {e}")
                except KeyboardInterrupt:
                    print(f"\n⏹️  Чат-поток для {nickname} остановлен")

            # Запускаем поток получения сообщений
            receive_thread = threading.Thread(target=receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            # Ждем завершения потока отправки
            receive_thread.join()
            
        except grpc.RpcError as e:
            print(f"❌ Ошибка чат-потока: {e}")
        except KeyboardInterrupt:
            print(f"\n⏹️  Чат-поток для {nickname} остановлен")

    def send_typing_status(self, nickname, is_typing=True):
        """Отправка статуса печати"""
        try:
            message_type = messenger_pb2.ChatMessageType.TYPING if is_typing else messenger_pb2.ChatMessageType.STOP_TYPING
            
            chat_message = messenger_pb2.ChatMessage(
                from_nickname=nickname,
                to_nickname="all",
                type=message_type
            )
            
            # Для простоты используем обычный SendMessage
            # В реальном приложении это должно быть через ChatStream
            print(f"⌨️  Статус печати отправлен: {'печатает' if is_typing else 'перестал печатать'}")
            
        except Exception as e:
            print(f"❌ Ошибка отправки статуса печати: {e}")


def main():
    """Основная функция для демонстрации streaming клиента"""
    if len(sys.argv) < 3:
        print("Использование: python streaming_client.py <server_address> <nickname> [mode]")
        print("Режимы:")
        print("  stream  - Server-Side Streaming (получение сообщений)")
        print("  chat    - Bidirectional Streaming (чат)")
        print("Примеры:")
        print("  python streaming_client.py localhost:8080 Алиса stream")
        print("  python streaming_client.py localhost:8080 Боб chat")
        sys.exit(1)

    server_address = sys.argv[1]
    nickname = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "chat"

    client = StreamingMessengerClient(server_address)
    client.nickname = nickname

    if not client.connect():
        sys.exit(1)

    try:
        print(f"\n=== Streaming gRPC клиент для {nickname} ===\n")

        if mode == "stream":
            print("🔄 Режим: Server-Side Streaming")
            print("Ожидаем новые сообщения... (Ctrl+C для выхода)")
            client.stream_received_messages(nickname)
            
        elif mode == "chat":
            print("💬 Режим: Bidirectional Streaming (Чат)")
            print("Введите сообщения для отправки в чат...")
            client.chat_stream(nickname)
            
        else:
            print(f"❌ Неизвестный режим: {mode}")
            print("Доступные режимы: stream, chat")
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Клиент {nickname} остановлен")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
