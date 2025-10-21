#!/usr/bin/env python3

import grpc
import sys
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
    if len(sys.argv) < 2:
        print("Использование: python simple_client.py <server_address>")
        print("Пример: python simple_client.py localhost:8080")
        sys.exit(1)

    server_address = sys.argv[1]
    client = MessengerClient(server_address)

    if not client.connect():
        sys.exit(1)
        
    nickname = input("Введите ваше имя: ")
    
    while True:
        command = input(f"{nickname} >> ")
        if command == "exit":
            break
        elif command == "send":
            to_nickname = input("Введите имя получателя: ")
            message = input("Введите сообщение: ")
            client.send_message(message, nickname, to_nickname)
        elif command == "received":
            client.get_received_messages(nickname)
        elif command == "sent":
            client.get_sent_messages(nickname)
        elif command == "help":
            print("help - показать список команд")
            print("exit - выйти из месенджера")
            print("send - отправить сообщение")
            print("received - получить полученные сообщения")
            print("sent - получить отправленные сообщения")
        else:
            print("Неизвестная команда")


if __name__ == "__main__":
    main()
