#!/usr/bin/env python3

import sys
import threading
import time
import os
from datetime import datetime
from generated import messenger_pb2
from generated import messenger_pb2_grpc
import grpc


class StreamingConsoleChat:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.nickname = None
        self.room_messages = {}
        self.running = False
        self.current_chat_id = None
        self.user_chats = {}
        self.chat_names = {}
        self.notifications = []
        self.user_colors = {}
        self.available_colors = [31, 32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96]
        self.stream_thread = None
        self.stream_stub = None
        
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
    
    def get_user_color(self, nickname):
        if nickname not in self.user_colors:
            import hashlib
            hash_value = int(hashlib.md5(nickname.encode()).hexdigest(), 16)
            color_index = hash_value % len(self.available_colors)
            self.user_colors[nickname] = self.available_colors[color_index]
        return self.user_colors[nickname]
    
    def send_message(self, message, chat_id=None):
        if chat_id is None:
            chat_id = self.current_chat_id
            
        if not chat_id:
            self.add_notification_to_list("❌ Выберите чат для отправки сообщения")
            return
            
        try:
            chat_message = messenger_pb2.ChatMessage(
                content=message,
                nickname=self.nickname,
                chat_id=chat_id,
                type=messenger_pb2.MESSAGE
            )
            
            if hasattr(self, 'message_queue'):
                self.message_queue.append(chat_message)
                
            self.add_room_message(chat_id, message, self.nickname, is_sent=True)
            
        except Exception as e:
            self.add_notification_to_list(f"❌ Ошибка отправки сообщения: {e}")
    
    def add_room_message(self, chat_id, content, nickname, is_sent=False):
        if chat_id not in self.room_messages:
            self.room_messages[chat_id] = []
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.room_messages[chat_id].append({
            'content': content,
            'nickname': nickname,
            'timestamp': timestamp,
            'is_sent': is_sent
        })
        print(f"[DEBUG] Добавлено сообщение в чат {chat_id}: {content} от {nickname}")
    
    def add_notification_to_list(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.notifications.append(f"🔔 [{timestamp}] {message}")
        if len(self.notifications) > 20:
            self.notifications = self.notifications[-20:]
    
    def get_user_chats(self):
        try:
            request = messenger_pb2.GetUserChatsRequest(nickname=self.nickname)
            response = self.stub.GetUserChats(request)
            
            self.user_chats = {chat.chat_id: chat for chat in response.chats}
            
            for chat_id in self.user_chats.keys():
                if chat_id not in self.chat_names:
                    self.chat_names[chat_id] = f"Chat {chat_id}"
            
            return response.chats
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка получения чатов: {e}")
            return []
    
    def create_chat(self, name):
        try:
            request = messenger_pb2.CreateChatRequest(name=name, nickname=self.nickname)
            response = self.stub.CreateChat(request)
            
            chat_id = response.chat_id
            self.chat_names[chat_id] = name
            
            if hasattr(self, 'message_queue'):
                chat_message = messenger_pb2.ChatMessage(
                    content=f"Создан чат: {name}",
                    nickname=self.nickname,
                    chat_id=chat_id,
                    type=messenger_pb2.CHAT_CREATED
                )
                self.message_queue.append(chat_message)
            
            self.add_notification_to_list(f"✅ Создан чат: {name} (ID: {chat_id})")
            return chat_id
            
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка создания чата: {e}")
            return None
    
    def join_chat(self, chat_id):
        try:
            request = messenger_pb2.JoinChatRequest(chat_id=chat_id, nickname=self.nickname)
            response = self.stub.JoinChat(request)
            
            if response.success:
                if hasattr(self, 'message_queue'):
                    self.add_notification_to_list(f"Sending user joined message to stream: {self.nickname} {chat_id}")
                    chat_message = messenger_pb2.ChatMessage(
                        content=f"Пользователь {self.nickname} присоединился к чату",
                        nickname=self.nickname,
                        chat_id=chat_id,
                        type=messenger_pb2.USER_JOINED
                    )
                    self.message_queue.append(chat_message)
                else:
                    self.add_notification_to_list(f"❌ Не удалось отправить уведомление о присоединении к чату")
                
                self.add_notification_to_list(f"✅ Присоединились к чату {self.chat_names.get(chat_id, chat_id)}")
                self.get_user_chats()
                return True
            else:
                self.add_notification_to_list(f"❌ Не удалось присоединиться к чату")
                return False
                
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка присоединения к чату: {e}")
            return False
    
    def leave_chat(self, chat_id):
        try:
            request = messenger_pb2.LeaveChatRequest(chat_id=chat_id, nickname=self.nickname)
            response = self.stub.LeaveChat(request)
            
            if response.success:
                if hasattr(self, 'message_queue'):
                    chat_message = messenger_pb2.ChatMessage(
                        content=f"Пользователь {self.nickname} покинул чат",
                        nickname=self.nickname,
                        chat_id=chat_id,
                        type=messenger_pb2.USER_LEFT
                    )
                    self.message_queue.append(chat_message)
                
                self.add_notification_to_list(f"✅ Покинули чат {self.chat_names.get(chat_id, chat_id)}")
                return True
            else:
                self.add_notification_to_list(f"❌ Не удалось покинуть чат")
                return False
                
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка выхода из чата: {e}")
            return False
    
    def switch_chat(self, chat_id):
        """Переключиться на чат"""
        if chat_id not in self.user_chats:
            self.add_notification_to_list("❌ Вы не состоите в этом чате")
            return False
        
        if hasattr(self, 'message_queue'):
            chat_message = messenger_pb2.ChatMessage(
                content=f"Пользователь {self.nickname} вошел в чат",
                nickname=self.nickname,
                chat_id=chat_id,
                type=messenger_pb2.USER_GOT_IN
            )
            self.message_queue.append(chat_message)
        
        self.current_chat_id = chat_id
        chat_name = self.chat_names.get(chat_id, chat_id)
        self.add_notification_to_list(f"✅ Переключились в чат: {chat_name} ({chat_id})")
        
        self.get_chat_messages(chat_id)
        return True
    
    def get_chat_messages(self, chat_id):
        try:
            request = messenger_pb2.GetMessagesRequest(chat_id=chat_id)
            response = self.stub.GetMessages(request)
            
            self.room_messages[chat_id] = []
            
            for msg in response.messages:
                self.add_room_message(chat_id, msg.content, msg.nickname)
                self.get_user_color(msg.nickname)
                
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка получения сообщений: {e}")
    
    def start_streaming(self):
        try:
            self.message_queue = []
            self.heartbeat_running = True
            
            connect_message = messenger_pb2.ChatMessage(
                content=f"Пользователь {self.nickname} подключился",
                nickname=self.nickname,
                chat_id="",
                type=messenger_pb2.USER_CONNECTED
            )
            self.message_queue.append(connect_message)
            
            def message_iterator():
                last_heartbeat = time.time()
                while self.heartbeat_running:
                    if self.message_queue:
                        yield self.message_queue.pop(0)
                    else:
                        current_time = time.time()
                        if current_time - last_heartbeat > 30:
                            heartbeat_message = messenger_pb2.ChatMessage(
                                content="heartbeat",
                                nickname=self.nickname,
                                chat_id="",
                                type=messenger_pb2.USER_CONNECTED
                            )
                            yield heartbeat_message
                            last_heartbeat = current_time
                        else:
                            time.sleep(0.1)
            
            self.stream_stub = self.stub.ChatStream(message_iterator())
            
            self.stream_thread = threading.Thread(target=self.stream_receiver, daemon=True)
            self.stream_thread.start()
            
            self.add_notification_to_list("🔄 Стриминг запущен")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска стриминга: {e}")
            self.add_notification_to_list(f"❌ Ошибка запуска стриминга: {e}")
            return False
    
    def stream_receiver(self):
        try:
            for message in self.stream_stub:
                if message.type == messenger_pb2.MESSAGE:
                    print(f"\n[DEBUG] Получено сообщение: {message.content} от {message.nickname} в чат {message.chat_id}")
                    self.add_room_message(message.chat_id, message.content, message.nickname)
                    self.refresh_display()
                elif message.type == messenger_pb2.USER_JOINED:
                    self.add_notification_to_list(f"👋 {message.nickname} присоединился к чату {message.chat_id}")
                    self.refresh_display()
                elif message.type == messenger_pb2.USER_LEFT:
                    self.add_notification_to_list(f"👋 {message.nickname} покинул чат {message.chat_id}")
                    self.refresh_display()
                elif message.type == messenger_pb2.CHAT_CREATED:
                    self.add_notification_to_list(f"🆕 {message.content}")
                    self.refresh_display()
                elif message.type == messenger_pb2.USER_GOT_IN:
                    self.add_notification_to_list(f"🚪 {message.nickname} вошел в чат {message.chat_id}")
                    self.refresh_display()
                elif message.type == messenger_pb2.SET_TTL_TO_CHAT:
                    ttl_text = ""
                    if message.HasField('ttl'):
                        ttl_minutes = message.ttl
                        ttl_text = f"⏱️ {message.nickname} установил TTL на {ttl_minutes} минут для чата {message.chat_id}"
                    else:
                        ttl_text = f"⏱️ {message.nickname} установил TTL для чата {message.chat_id}"
                    self.add_notification_to_list(ttl_text)
                    if message.content:
                        self.add_room_message(message.chat_id, message.content, message.nickname)
                    self.refresh_display()
                
                self.get_user_color(message.nickname)
                
        except Exception as e:
            self.add_notification_to_list(f"❌ Ошибка стриминга: {e}")
    
    def stop_streaming(self):
        self.heartbeat_running = False
        
        if hasattr(self, 'message_queue') and self.message_queue is not None:
            for chat_id in self.user_chats.keys():
                leave_message = messenger_pb2.ChatMessage(
                    content=f"Пользователь {self.nickname} покинул чат",
                    nickname=self.nickname,
                    chat_id=chat_id,
                    type=messenger_pb2.USER_LEFT
                )
                self.message_queue.append(leave_message)
            
            time.sleep(0.5)
        
        if self.stream_stub:
            try:
                self.stream_stub.cancel()
            except:
                pass
            self.stream_stub = None
        
        if self.stream_thread:
            self.stream_thread.join(timeout=1)
            self.stream_thread = None
    
    def display_messages(self):
        self.clear_screen()
        
        print("=" * 80)
        print(f"🎯 СТРИМИНГОВЫЙ ЧАТ - {self.nickname}")
        print("=" * 80)
        
        if self.notifications:
            print("🔔 УВЕДОМЛЕНИЯ:")
            for notification in self.notifications[-5:]:
                print(f"  {notification}")
            print()
        
        if self.current_chat_id is None:
            print("🏠 ГЛАВНОЕ МЕНЮ")
            print("=" * 40)
            print("Доступные действия:")
            print("  /create <название> - создать чат")
            print("  /join <chat_id> - присоединиться к чату")
            print("  /chats - список ваших чатов")
            print("  /help - помощь")
            print("  /exit - выход")
            print()
        else:
            chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
            print(f"💬 ЧАТ: {chat_name} ({self.current_chat_id})")
            print("=" * 40)
            
            if self.current_chat_id in self.room_messages:
                for msg in self.room_messages[self.current_chat_id][-20:]:  # Последние 20 сообщений
                    color = self.get_user_color(msg['nickname'])
                    if msg['is_sent']:
                        print(f"  \033[{color}m[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\033[0m")
                    else:
                        print(f"  \033[{color}m[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\033[0m")
            print()
        
        print("-" * 80)
        if self.current_chat_id:
            print(f"💬 Введите сообщение или команду (чат: {self.chat_names.get(self.current_chat_id, self.current_chat_id)}): ", end="", flush=True)
        else:
            print("💬 Введите команду: ", end="", flush=True)
    
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def refresh_display(self):
        if self.current_chat_id:
            print(f"[DEBUG] Обновляем отображение для чата {self.current_chat_id}")
            self.display_messages()
    
    def show_help(self):
        print("\n📖 СПРАВКА ПО КОМАНДАМ:")
        print("=" * 50)
        print("🏠 ГЛАВНОЕ МЕНЮ:")
        print("  /create <название>  - создать новый чат")
        print("  /join <chat_id>     - присоединиться к чату")
        print("  /chats             - список ваших чатов")
        print("  /home              - вернуться в главное меню")
        print("  /notifications     - очистить все уведомления")
        print("  /colors            - показать цвета пользователей")
        print("  /help              - показать эту справку")
        print("  /exit              - выйти из программы")
        print()
        print("💬 В ЧАТЕ:")
        print("  /leave             - покинуть текущий чат")
        print("  /history           - показать историю сообщений")
        print("  /current           - информация о текущем чате")
        print("  /ttl <минуты>      - установить TTL для чата (в минутах)")
        print()
        print("🔄 СТРИМИНГ:")
        print("  Все действия автоматически отправляются через стрим")
        print("  Сообщения приходят в реальном времени")
        print("=" * 50)
    
    def show_status(self):
        print("\n📊 СТАТУС:")
        print("=" * 30)
        print(f"👤 Пользователь: {self.nickname}")
        print(f"🌐 Сервер: {self.server_address}")
        print(f"💬 Текущий чат: {self.current_chat_id or 'Главное меню'}")
        print(f"📝 Всего чатов: {len(self.user_chats)}")
        print(f"🔔 Уведомлений: {len(self.notifications)}")
        print(f"🎨 Пользователей с цветами: {len(self.user_colors)}")
        print(f"🔄 Стриминг: {'Активен' if self.stream_stub else 'Неактивен'}")
        print("=" * 30)
    
    def process_command(self, user_input):
        parts = user_input.strip().split()
        if not parts:
            return
        
        command = parts[0].lower()
        
        if command == "/help":
            self.show_help()
            return
        elif command == "/exit":
            self.running = False
            return
        elif command == "/status":
            self.show_status()
            return
        elif command == "/home":
            self.current_chat_id = None
            self.add_notification_to_list("🏠 Перешли в главное меню")
            return
        elif command == "/chats":
            chats = self.get_user_chats()
            if chats:
                print("\n📋 ВАШИ ЧАТЫ:")
                print("=" * 40)
                for chat in chats:
                    chat_name = self.chat_names.get(chat.chat_id, chat.chat_id)
                    new_messages = chat.new_messages
                    status = f" ({new_messages} новых)" if new_messages > 0 else ""
                    print(f"  • {chat_name} (ID: {chat.chat_id}){status}")
                print("=" * 40)
            else:
                print("\n📋 У вас пока нет чатов")
            return
        elif command == "/create":
            if len(parts) < 2:
                print("❌ Укажите название чата: /create <название>")
                return
            chat_name = " ".join(parts[1:])
            chat_id = self.create_chat(chat_name)
            if chat_id:
                self.get_user_chats()
        elif command == "/join":
            if len(parts) < 2:
                print("❌ Укажите ID чата: /join <chat_id>")
                return
            chat_id = parts[1]
            if self.join_chat(chat_id):
                self.switch_chat(chat_id)
        elif command == "/leave":
            if not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            if self.leave_chat(self.current_chat_id):
                self.current_chat_id = None
                self.add_notification_to_list("🏠 Вернулись в главное меню")
        elif command == "/history":
            if not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            self.get_chat_messages(self.current_chat_id)
            print(f"\n📜 История сообщений чата {self.chat_names.get(self.current_chat_id, self.current_chat_id)} обновлена")
            return
        elif command == "/current":
            if not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
            chat_stats = self.user_chats.get(self.current_chat_id)
            new_messages = chat_stats.new_messages if chat_stats else 0
            print(f"\n💬 ТЕКУЩИЙ ЧАТ:")
            print(f"  Название: {chat_name}")
            print(f"  ID: {self.current_chat_id}")
            print(f"  Новых сообщений: {new_messages}")
            print(f"  Всего сообщений: {len(self.room_messages.get(self.current_chat_id, []))}")
            return
        elif command == "/notifications":
            self.notifications = []
            print("\n✅ Уведомления очищены")
            return
        elif command == "/colors":
            if self.user_colors:
                print("\n🎨 ЦВЕТА ПОЛЬЗОВАТЕЛЕЙ:")
                print("=" * 40)
                for nickname, color in self.user_colors.items():
                    print(f"  \033[{color}m{nickname}\033[0m")
                print("=" * 40)
            else:
                print("\n🎨 Пользователи с цветами не найдены")
            return
        elif command == "/ttl":
            if not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            if len(parts) < 2:
                print("❌ Укажите количество минут: /ttl <минуты>")
                return
            try:
                minutes = int(parts[1])
                if minutes < 0:
                    print("❌ Количество минут должно быть положительным числом")
                    return
                
                # Отправляем сообщение с типом SET_TTL_TO_CHAT
                if hasattr(self, 'message_queue') and self.message_queue is not None:
                    ttl_message = messenger_pb2.ChatMessage(
                        content=f"TTL установлен на {minutes} минут",
                        nickname=self.nickname,
                        chat_id=self.current_chat_id,
                        type=messenger_pb2.SET_TTL_TO_CHAT,
                        ttl=minutes
                    )
                    self.message_queue.append(ttl_message)
                    self.add_notification_to_list(f"⏱️ TTL установлен на {minutes} минут для чата")
                else:
                    print("❌ Стриминг не активен")
            except ValueError:
                print("❌ Количество минут должно быть числом")
            return
        else:
            if self.current_chat_id:
                self.send_message(user_input)
            else:
                print("❌ Выберите чат для отправки сообщения")
    
    def run(self):
        print("🎯 СТРИМИНГОВЫЙ ЧАТ")
        print("=" * 50)
        
        self.nickname = input("Введите ваше имя: ").strip()
        if not self.nickname:
            print("❌ Имя не может быть пустым")
            return
        
        if not self.connect():
            print("❌ Не удалось подключиться к серверу")
            return
        
        self.get_user_color(self.nickname)
                
        if not self.start_streaming():
            return
        
        self.get_user_chats()
        
        self.add_notification_to_list(f"👋 Добро пожаловать, {self.nickname}!")
        self.add_notification_to_list("🔄 Стриминг активен - сообщения приходят в реальном времени")
        
        self.running = True
        
        try:
            while self.running:
                no_update_commands = ["/help", "/status", "/rooms", "/history", "/current", "/notifications", "/home", "/colors"]
                
                self.display_messages()
                user_input = input()
                
                if not user_input.strip():
                    continue
                
                self.process_command(user_input)
                
                if self.running and not any(user_input.strip().startswith(cmd) for cmd in no_update_commands):
                    self.display_messages()
                    
        except KeyboardInterrupt:
            print("\n👋 Выход из чата...")
        finally:
            self.stop_streaming()
            self.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Стриминговый консольный чат')
    parser.add_argument('--server', default='localhost:8080', help='Адрес сервера (по умолчанию: localhost:8080)')
    
    args = parser.parse_args()
    
    chat = StreamingConsoleChat(args.server)
    chat.run()