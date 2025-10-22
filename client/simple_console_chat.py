#!/usr/bin/env python3

import sys
import threading
import time
import os
from datetime import datetime
from generated import messenger_pb2
from generated import messenger_pb2_grpc
import grpc


class SimpleConsoleChat:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.nickname = None
        self.messages = []  # Общие сообщения
        self.room_messages = {}  # Сообщения по комнатам {chat_id: [messages]}
        self.running = False
        self.last_message_time = time.time()
        self.current_chat_id = None  # Текущий чат ID
        self.user_chats = {}  # Информация о чатах пользователя {chat_id: ChatStats}
        self.chat_names = {}  # Названия чатов {chat_id: name}
        self.notifications = []  # Список уведомлений
        self.last_notification_check = time.time()  # Время последней проверки уведомлений
        self.user_colors = {}  # Цвета пользователей {nickname: color_code}
        self.available_colors = [31, 32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96]  # Доступные цвета ANSI
        
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
    
    def send_message(self, message, chat_id=None):
        """Отправка сообщения"""
        if chat_id is None:
            chat_id = self.current_chat_id
            
        if not chat_id:
            self.add_notification("❌ Не выбран чат. Используйте /join <chat_id>")
            return None
            
        try:
            request = messenger_pb2.SendMessageRequest(
                message=message,
                chat_id=chat_id,
                nickname=self.nickname
            )
            
            response = self.stub.SendMessage(request)
            # Добавляем сообщение в историю текущего чата
            chat_name = self.chat_names.get(chat_id, chat_id)
            self.add_room_message(f"📤 [{self.nickname}]: {message}", "sent", chat_id, self.nickname)
            return response.message_id
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка отправки: {e}")
            return None
    
    def get_user_chats(self):
        """Получение списка чатов пользователя с статистикой"""
        try:
            request = messenger_pb2.GetUserChatsRequest(nickname=self.nickname)
            response = self.stub.GetUserChats(request)
            
            # Проверяем, есть ли изменения в статистике
            chats_with_new_messages = []
            total_new_messages = 0
            
            for chat_stats in response.chats:
                old_stats = self.user_chats.get(chat_stats.chat_id)
                self.user_chats[chat_stats.chat_id] = chat_stats
                
                if chat_stats.new_messages > 0:
                    total_new_messages += chat_stats.new_messages
                    # Добавляем только если количество изменилось
                    if not old_stats or old_stats.new_messages != chat_stats.new_messages:
                        chats_with_new_messages.append(chat_stats)
            
            # Показываем уведомления только при изменениях
            if chats_with_new_messages:
                # Если пользователь в главном меню (не в чате), показываем все уведомления
                # Если пользователь в конкретном чате, показываем уведомления только для других чатов
                if self.current_chat_id is None:
                    # В главном меню - показываем все уведомления
                    filtered_chats = chats_with_new_messages
                else:
                    # В чате - исключаем текущий чат
                    filtered_chats = [chat for chat in chats_with_new_messages if chat.chat_id != self.current_chat_id]
                
                if filtered_chats:
                    # Проверяем, есть ли уже заголовок уведомлений в списке
                    header_text = "📨 Новые сообщения в чатах:" if self.current_chat_id is None else "📨 Новые сообщения в других чатах:"
                    has_header = any(header_text in notification for notification in self.notifications)
                    
                    if not has_header:
                        self.add_notification_to_list(header_text)
                    
                    for chat_stats in filtered_chats:
                        chat_name = self.chat_names.get(chat_stats.chat_id, chat_stats.chat_id)
                        # Проверяем, есть ли уже уведомление об этом чате
                        chat_notification = f"   • {chat_name}: {chat_stats.new_messages} новых"
                        has_chat_notification = any(chat_notification in notification for notification in self.notifications)
                        
                        if not has_chat_notification:
                            self.add_notification_to_list(chat_notification)
            
            return response.chats
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка получения чатов: {e}")
            return []
    
    def get_chat_messages(self, chat_id):
        """Получение сообщений конкретного чата"""
        try:
            request = messenger_pb2.GetMessagesRequest(chat_id=chat_id)
            response = self.stub.GetMessages(request)
            
            # Предварительно инициализируем цвета для всех пользователей в чате
            for msg in response.messages:
                self.get_user_color(msg.nickname)
            
            # Очищаем старые сообщения чата и загружаем новые
            self.room_messages[chat_id] = []
            for msg in response.messages:
                self.add_room_message(f"📥 [{msg.nickname}]: {msg.content}", "received", chat_id, msg.nickname)
            
            return response.messages
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка получения сообщений чата: {e}")
            return []
    
    def set_messages_read(self, chat_id):
        """Отметить сообщения чата как прочитанные"""
        try:
            request = messenger_pb2.SetMessagesReadRequest(
                chat_id=chat_id,
                nickname=self.nickname
            )
            response = self.stub.SetMessagesRead(request)
            
            if response.success:
                # Обновляем статистику - убираем непрочитанные сообщения
                if chat_id in self.user_chats:
                    self.user_chats[chat_id].new_messages = 0
            return response.success
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка отметки сообщений как прочитанных: {e}")
            return False
    
    def create_chat(self, chat_name):
        """Создать новый чат"""
        try:
            request = messenger_pb2.CreateChatRequest(
                name=chat_name,
                nickname=self.nickname
            )
            response = self.stub.CreateChat(request)
            
            if response.chat_id:
                self.chat_names[response.chat_id] = chat_name
                self.add_notification(f"✅ Создан чат '{chat_name}' с ID: {response.chat_id}")
                return response.chat_id
            else:
                self.add_notification(f"❌ Сервер не вернул chat_id")
                return None
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка создания чата: {e}")
            return None
        except Exception as e:
            self.add_notification(f"❌ Неожиданная ошибка создания чата: {e}")
            return None
    
    def join_chat(self, chat_id):
        """Вступить в чат"""
        try:
            request = messenger_pb2.JoinChatRequest(
                chat_id=chat_id,
                nickname=self.nickname
            )
            response = self.stub.JoinChat(request)
            
            if response.success:
                self.add_notification(f"✅ Успешно вступили в чат {chat_id}")
                # Обновляем список чатов после успешного вступления
                self.get_user_chats()
                return True
            else:
                self.add_notification(f"❌ Не удалось вступить в чат {chat_id}")
                return False
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка вступления в чат: {e}")
            return False
    
    def leave_chat(self, chat_id):
        """Покинуть чат"""
        try:
            request = messenger_pb2.LeaveChatRequest(
                chat_id=chat_id,
                nickname=self.nickname
            )
            response = self.stub.LeaveChat(request)
            
            if response.success:
                self.add_notification(f"✅ Покинули чат {chat_id}")
                # Удаляем из локального кэша
                if chat_id in self.user_chats:
                    del self.user_chats[chat_id]
                if chat_id in self.room_messages:
                    del self.room_messages[chat_id]
                if chat_id in self.chat_names:
                    del self.chat_names[chat_id]
                return True
            else:
                self.add_notification(f"❌ Не удалось покинуть чат {chat_id}")
                return False
        except grpc.RpcError as e:
            self.add_notification(f"❌ Ошибка выхода из чата: {e}")
            return False
    
    def add_message(self, message, msg_type="info"):
        """Добавление сообщения в общую историю"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.messages.append((formatted_message, msg_type))
        
        # Ограничиваем количество сообщений
        if len(self.messages) > 100:
            self.messages = self.messages[-50:]
    
    def add_room_message(self, message, msg_type="info", chat_id=None, nickname=None):
        """Добавление сообщения в конкретный чат"""
        if chat_id is None:
            chat_id = self.current_chat_id
            
        if chat_id not in self.room_messages:
            self.room_messages[chat_id] = []
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Сохраняем сообщение с информацией о пользователе и типе
        self.room_messages[chat_id].append((formatted_message, msg_type, nickname))
        
        # Ограничиваем количество сообщений в чате
        if len(self.room_messages[chat_id]) > 100:
            self.room_messages[chat_id] = self.room_messages[chat_id][-50:]
            
        # Если это текущий чат, также добавляем в общие сообщения
        if chat_id == self.current_chat_id:
            self.add_message(message, msg_type)
    
    def switch_chat(self, chat_id):
        """Переключение на другой чат"""
        # Отмечаем сообщения как прочитанные при переходе в чат
        self.set_messages_read(chat_id)
        
        # Загружаем сообщения чата с сервера
        self.get_chat_messages(chat_id)
        
        self.current_chat_id = chat_id
        chat_name = self.chat_names.get(chat_id, chat_id)
        self.add_notification(f"✅ Переключились в чат: {chat_name} ({chat_id})")
        
        # Удаляем старые уведомления об этом чате
        self.clear_chat_notifications(chat_id)
        
        # Показываем историю сообщений этого чата
        if chat_id in self.room_messages and self.room_messages[chat_id]:
            self.add_notification(f"📜 История чата '{chat_name}': {len(self.room_messages[chat_id])} сообщений")
        
        return True
    
    def get_chat_history(self, chat_id=None):
        """Получение истории сообщений чата"""
        if chat_id is None:
            chat_id = self.current_chat_id
            
        if chat_id not in self.room_messages:
            return []
        return self.room_messages[chat_id]
    
    def add_notification(self, notification):
        """Добавление уведомления (для немедленного отображения)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_notification = f"🔔 [{timestamp}] {notification}"
        print(f"\n{formatted_notification}")
    
    def add_notification_to_list(self, notification):
        """Добавление уведомления в список для отображения в отдельной области"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_notification = f"🔔 [{timestamp}] {notification}"
        self.notifications.append(formatted_notification)
        
        # Ограничиваем количество уведомлений
        if len(self.notifications) > 10:
            self.notifications = self.notifications[-5:]
    
    def get_user_color(self, nickname):
        """Получить цвет для пользователя"""
        if nickname not in self.user_colors:
            # Назначаем цвет на основе хеша имени пользователя для стабильности
            import hashlib
            hash_value = int(hashlib.md5(nickname.encode()).hexdigest(), 16)
            color_index = hash_value % len(self.available_colors)
            self.user_colors[nickname] = self.available_colors[color_index]
        return self.user_colors[nickname]
    
    def clear_chat_notifications(self, chat_id):
        """Удалить уведомления о конкретном чате"""
        chat_name = self.chat_names.get(chat_id, chat_id)
        
        # Удаляем уведомления о новых сообщениях в этом чате
        self.notifications = [
            notification for notification in self.notifications 
            if not (
                ("новых" in notification and chat_name in notification) or
                ("Новые сообщения" in notification and chat_name in notification)
            )
        ]
        
        # Проверяем, остались ли уведомления о чатах с новыми сообщениями
        has_chat_notifications = any("новых" in notification and "•" in notification for notification in self.notifications)
        
        # Если нет уведомлений о чатах, удаляем заголовки
        if not has_chat_notifications:
            self.notifications = [
                notification for notification in self.notifications 
                if "Новые сообщения в чатах" not in notification and "Новые сообщения в других чатах" not in notification
            ]
    
    def clear_screen(self):
        """Очистка экрана"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def display_messages(self):
        """Отображение сообщений"""
        self.clear_screen()
        
        # Заголовок
        print("=" * 80)
        if self.current_chat_id:
            chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
            print(f"📨 КОНСОЛЬНЫЙ ЧАТ - Чат: \033[93m{chat_name}\033[0m ({self.current_chat_id})")
        else:
            print("🏠 КОНСОЛЬНЫЙ ЧАТ - Главное меню")
        print("=" * 80)
        
        # Область уведомлений
        if self.notifications:
            print("\n🔔 УВЕДОМЛЕНИЯ:")
            for notification in self.notifications[-5:]:  # Показываем последние 5 уведомлений
                print(f"\033[96m{notification}\033[0m")  # Голубой цвет для уведомлений
            print("-" * 80)
        
        # Показываем сообщения текущего чата или главное меню
        if self.current_chat_id:
            chat_messages = self.get_chat_history(self.current_chat_id)
            
            if not chat_messages:
                print("\n📭 В этом чате пока нет сообщений...")
            else:
                # Показываем последние 15 сообщений текущего чата (меньше из-за области уведомлений)
                recent_messages = chat_messages[-15:]
                for message_data in recent_messages:
                    if len(message_data) >= 3:
                        message, msg_type, nickname = message_data
                    else:
                        message, msg_type = message_data
                        nickname = None
                    
                    if msg_type == "received" and nickname:
                        # Цвет пользователя для полученных сообщений
                        user_color = self.get_user_color(nickname)
                        print(f"\033[{user_color}m{message}\033[0m")
                    elif msg_type == "sent" and nickname:
                        # Цвет пользователя для отправленных сообщений (немного тусклее)
                        user_color = self.get_user_color(nickname)
                        print(f"\033[{user_color};2m{message}\033[0m")  # Тусклый цвет
                    elif msg_type == "error":
                        print(f"\033[91m{message}\033[0m")  # Красный для ошибок
                    else:
                        print(message)  # Обычный цвет для информационных
        else:
            # Главное меню
            print("\n🏠 ДОБРО ПОЖАЛОВАТЬ В ГЛАВНОЕ МЕНЮ!")
            print("\n📋 Доступные действия:")
            print("• /create <название> - создать новый чат")
            print("• /join <chat_id>    - перейти в существующий чат")
            print("• /chats             - показать все ваши чаты")
            print("• /help              - показать справку")
            print("• /status            - показать статус подключения")
            print("\n💡 Используйте команды выше для навигации")
        
        print("\n" + "=" * 80)
        
        # Показываем информацию о чатах
        if self.user_chats:
            if self.current_chat_id:
                print(f"🏠 Ваши чаты:")
            else:
                print(f"📋 ВАШИ ЧАТЫ:")
            for chat_id, chat_stats in self.user_chats.items():
                chat_name = self.chat_names.get(chat_id, chat_id)
                new_msgs = chat_stats.new_messages
                current = " ← текущий" if chat_id == self.current_chat_id else ""
                new_indicator = f" ({new_msgs} новых)" if new_msgs > 0 else ""
                print(f"   • {chat_name} ({chat_id}){new_indicator}{current}")
        else:
            if self.current_chat_id:
                print("🏠 У вас пока нет чатов. Используйте /create для создания чата")
            else:
                print("📋 У вас пока нет чатов. Используйте /create для создания чата")
        
        print("=" * 80)
    
    def show_help(self):
        """Показать справку"""
        print("\n" + "="*80)
        print("📋 КОМАНДЫ ЧАТА:")
        print("="*80)
        print("🏠 КОМАНДЫ ЧАТОВ:")
        print("/join <chat_id>     - перейти в чат")
        print("/create <название>  - создать новый чат")
        print("/leave <chat_id>    - покинуть чат")
        print("/chats              - показать все ваши чаты")
        print("/history [chat_id]  - показать историю чата")
        print("/current            - показать текущий чат")
        print("/colors             - показать цвета пользователей")
        print()
        print("💬 ОСНОВНЫЕ КОМАНДЫ:")
        print("/help               - показать эту справку")
        print("/exit               - выйти из чата")
        print("/home               - вернуться в главное меню")
        print("/refresh            - обновить чаты и сообщения")
        print("/clear              - очистить экран")
        print("/notifications      - очистить все уведомления")
        print("/status             - показать статус подключения")
        print("="*80)
        print("💬 Для отправки сообщения просто введите текст")
        print("   (сообщение отправится в текущий чат)")
        print("="*80)
    
    def show_status(self):
        """Показать статус"""
        print("\n" + "="*80)
        print("📊 СТАТУС ПОДКЛЮЧЕНИЯ:")
        print("="*80)
        print(f"👤 Пользователь: {self.nickname}")
        print(f"🌐 Сервер: {self.server_address}")
        if self.current_chat_id:
            chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
            print(f"📍 Текущий чат: {chat_name} ({self.current_chat_id})")
        else:
            print(f"📍 Текущий чат: не выбран")
        print(f"🏠 Ваших чатов: {len(self.user_chats)}")
        print(f"📨 Общих сообщений: {len(self.messages)}")
        print(f"📊 Сообщений по чатам:")
        for chat_id, chat_stats in self.user_chats.items():
            chat_name = self.chat_names.get(chat_id, chat_id)
            count = len(self.room_messages.get(chat_id, []))
            new_msgs = chat_stats.new_messages
            new_indicator = f" ({new_msgs} новых)" if new_msgs > 0 else ""
            print(f"   • {chat_name} ({chat_id}): {count} сообщений{new_indicator}")
        print(f"🔄 Статус: {'подключен' if self.channel else 'отключен'}")
        print("="*80)
    
    def process_command(self, command):
        """Обработка команд"""
        command = command.strip()
        
        if not command:
            return
        
        # Команды чатов
        if command.startswith("/join "):
            parts = command.split(" ", 1)
            if len(parts) >= 2:
                chat_id = parts[1].strip()
                # Сначала пытаемся вступить в чат
                if self.join_chat(chat_id):
                    # Если успешно вступили, переключаемся на чат
                    if self.switch_chat(chat_id):
                        self.display_messages()
                else:
                    # Если не удалось вступить, возможно пользователь уже в чате
                    # Попробуем просто переключиться
                    if chat_id in self.user_chats:
                        if self.switch_chat(chat_id):
                            self.display_messages()
                    else:
                        self.add_notification(f"❌ Не удалось вступить в чат {chat_id}")
            else:
                self.add_notification("❌ Использование: /join <chat_id>")
            return
            
        elif command.startswith("/create "):
            parts = command.split(" ", 1)
            if len(parts) >= 2:
                chat_name = parts[1].strip()
                chat_id = self.create_chat(chat_name)
                if chat_id:
                    # Обновляем список чатов
                    self.get_user_chats()
                    # Автоматически переходим в созданный чат
                    self.switch_chat(chat_id)
                    self.display_messages()
            else:
                self.add_notification("❌ Использование: /create <название>")
            return
            
        elif command.startswith("/leave "):
            parts = command.split(" ", 1)
            if len(parts) >= 2:
                chat_id = parts[1].strip()
                if self.leave_chat(chat_id):
                    # Если покидаем текущий чат, сбрасываем текущий чат
                    if chat_id == self.current_chat_id:
                        self.current_chat_id = None
                    self.display_messages()
            else:
                self.add_notification("❌ Использование: /leave <chat_id>")
            return
            
        elif command == "/chats":
            print("\n" + "="*60)
            print("🏠 ВАШИ ЧАТЫ:")
            print("="*60)
            if not self.user_chats:
                print("📭 У вас пока нет чатов")
            else:
                for chat_id, chat_stats in self.user_chats.items():
                    chat_name = self.chat_names.get(chat_id, chat_id)
                    count = len(self.room_messages.get(chat_id, []))
                    new_msgs = chat_stats.new_messages
                    current = " ← текущий" if chat_id == self.current_chat_id else ""
                    new_indicator = f" ({new_msgs} новых)" if new_msgs > 0 else ""
                    print(f"• {chat_name} ({chat_id}): {count} сообщений{new_indicator}{current}")
            print("="*60)
            return
            
        elif command.startswith("/history "):
            parts = command.split(" ", 1)
            if len(parts) >= 2:
                chat_id = parts[1].strip()
            else:
                chat_id = self.current_chat_id
                
            if not chat_id:
                self.add_notification("❌ Не выбран чат")
                return
                
            history = self.get_chat_history(chat_id)
            chat_name = self.chat_names.get(chat_id, chat_id)
            print(f"\n📜 ИСТОРИЯ ЧАТА '{chat_name}' ({chat_id}):")
            print("="*70)
            if not history:
                print("📭 Сообщений нет")
            else:
                for message_data in history:
                    if len(message_data) >= 3:
                        message, msg_type, nickname = message_data
                    else:
                        message, msg_type = message_data
                        nickname = None
                    
                    if msg_type == "received" and nickname:
                        user_color = self.get_user_color(nickname)
                        print(f"\033[{user_color}m{message}\033[0m")
                    elif msg_type == "sent" and nickname:
                        user_color = self.get_user_color(nickname)
                        print(f"\033[{user_color};2m{message}\033[0m")  # Тусклый цвет
                    elif msg_type == "error":
                        print(f"\033[91m{message}\033[0m")
                    else:
                        print(message)
            print("="*70)
            return
            
        elif command == "/current":
            if self.current_chat_id:
                chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
                print(f"\n📍 Текущий чат: \033[93m{chat_name}\033[0m ({self.current_chat_id})")
                count = len(self.room_messages.get(self.current_chat_id, []))
                print(f"📊 Сообщений в чате: {count}")
            else:
                print("\n📍 Текущий чат: не выбран")
            return
            
        elif command == "/colors":
            print("\n🎨 ЦВЕТА ПОЛЬЗОВАТЕЛЕЙ:")
            print("="*50)
            if self.user_colors:
                for nickname, color_code in self.user_colors.items():
                    print(f"• {nickname}: \033[{color_code}m██████\033[0m")
            else:
                print("📭 Пока нет пользователей с назначенными цветами")
            print("="*50)
            return
        
        # Основные команды
        elif command == "/exit":
            self.running = False
        elif command == "/help":
            self.show_help()
            return
        elif command == "/home":
            self.current_chat_id = None
            self.add_notification("🏠 Возвращаемся в главное меню")
            self.display_messages()
            return
        elif command == "/refresh":
            # Обновляем список чатов и их статистику
            self.get_user_chats()
            # Если есть текущий чат, обновляем его сообщения
            if self.current_chat_id:
                self.get_chat_messages(self.current_chat_id)
            self.display_messages()
            return
        elif command == "/clear":
            # Очищаем только текущий чат
            if self.current_chat_id and self.current_chat_id in self.room_messages:
                self.room_messages[self.current_chat_id].clear()
            self.display_messages()
            return
        elif command == "/notifications":
            self.notifications.clear()
            self.add_notification("Уведомления очищены")
            return
        elif command == "/status":
            self.show_status()
            return
        else:
            # Обычное сообщение - отправляем в текущий чат
            self.send_message(command, self.current_chat_id)
    
    def message_polling_thread(self):
        """Поток для периодического получения новых сообщений"""
        while self.running:
            try:
                # Обновляем статистику чатов
                self.get_user_chats()
                # Обновляем сообщения текущего чата
                if self.current_chat_id:
                    self.get_chat_messages(self.current_chat_id)
                time.sleep(1)  # Проверяем новые сообщения каждые 3 секунды
            except Exception as e:
                self.add_notification(f"❌ Ошибка в потоке опроса: {e}")
                time.sleep(5)
    
    def run(self):
        """Основной цикл приложения"""
        self.running = True
        
        # Запускаем поток для получения сообщений
        polling_thread = threading.Thread(target=self.message_polling_thread, daemon=True)
        polling_thread.start()
        
        # Загружаем чаты пользователя при старте
        self.get_user_chats()
        
        # Инициализируем цвет для текущего пользователя
        self.get_user_color(self.nickname)
        
        # Приветственное сообщение
        self.add_notification(f"Добро пожаловать в консольный чат, {self.nickname}!")
        self.add_notification("Введите /help для получения справки")
        
        # Начальное отображение
        self.display_messages()
        
        # Основной цикл
        while self.running:
            try:
                # Показываем приглашение для ввода с указанием чата
                if self.current_chat_id:
                    chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
                    user_input = input(f"\n{self.nickname}@{chat_name}: ")
                else:
                    user_input = input(f"\n{self.nickname}: ")
                
                self.process_command(user_input)
                
                # Обновляем отображение только для определенных команд
                # Команды /help, /status, /chats, /history, /current, /notifications, /home, /colors не обновляют экран автоматически
                no_update_commands = ["/help", "/status", "/chats", "/history", "/current", "/notifications", "/home", "/colors"]
                if self.running and not any(user_input.strip().startswith(cmd) for cmd in no_update_commands):
                    self.display_messages()
                
            except KeyboardInterrupt:
                print("\n👋 Выход из чата...")
                self.running = False
            except EOFError:
                print("\n👋 Выход из чата...")
                self.running = False
            except Exception as e:
                self.add_notification(f"❌ Ошибка: {e}")
        
        # Завершение
        self.disconnect()


def main():
    if len(sys.argv) < 2:
        print("Использование: python simple_console_chat.py <server_address>")
        print("Пример: python simple_console_chat.py localhost:8080")
        sys.exit(1)
    
    server_address = sys.argv[1]
    
    # Получаем никнейм пользователя
    nickname = input("Введите ваше имя: ").strip()
    if not nickname:
        print("❌ Никнейм не может быть пустым!")
        sys.exit(1)
    
    # Создаем и запускаем чат
    chat = SimpleConsoleChat(server_address)
    chat.nickname = nickname
    
    if not chat.connect():
        print(f"❌ Не удалось подключиться к серверу {server_address}")
        sys.exit(1)
    
    try:
        chat.run()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        print("👋 До свидания!")


if __name__ == "__main__":
    main()
