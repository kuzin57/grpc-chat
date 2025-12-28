#!/usr/bin/env python3

import sys
import threading
import time
import os
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp
from generated import messenger_pb2
from generated import messenger_pb2_grpc
import grpc


class StreamingConsoleChat:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.nickname = None
        self.running = False
        self.current_chat_id = None
        self.user_chats = {}
        self.chat_names = {}
        self.notifications = []
        self.user_colors = {}
        self.available_colors = [31, 32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96]
        self.stream_thread = None
        self.stream_stub = None
        self.search_mode = False
        self.search_scroll_id = None
        self.search_results = []
        self.search_scroll_position = 0  # позиция скроллинга в результатах поиска
        # Скроллинг сообщений
        self.cached_messages = {}  # chat_id -> список всех загруженных сообщений
        self.scroll_position = {}  # chat_id -> текущая позиция просмотра (индекс)
        self.scroll_scroll_id = {}  # chat_id -> scrollID для текущего скроллинга
        self.scroll_offset = {}  # chat_id -> текущий offset для подгрузки
        self.messages_per_page = 20  # количество сообщений на странице
        
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
    
    def timestamp_to_datetime(self, timestamp):
        """Конвертирует protobuf Timestamp в datetime объект"""
        if timestamp is None:
            return datetime.now()
        return datetime.fromtimestamp(timestamp.seconds + timestamp.nanos / 1e9)
    
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
            
            # Оптимистичное обновление: добавляем сообщение в кэш сразу
            if chat_id not in self.cached_messages:
                self.cached_messages[chat_id] = []
            
            now = datetime.now()
            # Временно добавляем сообщение с пустым ID (будет заменено при получении через стрим)
            temp_message = {
                'id': '',  # Будет установлен когда придет с сервера
                'content': message,
                'nickname': self.nickname,
                'created_at': now,
                'timestamp': now.strftime("%H:%M:%S")
            }
            self.cached_messages[chat_id].append(temp_message)
            
            # Обновляем позицию скроллинга чтобы показать новое сообщение
            scroll_pos = self.scroll_position.get(chat_id, 0)
            total = len(self.cached_messages[chat_id])
            if scroll_pos >= total - self.messages_per_page - 1:
                self.scroll_position[chat_id] = max(0, total - self.messages_per_page)
            
            if hasattr(self, 'message_queue'):
                self.message_queue.append(chat_message)
            
            self.refresh_display()
            
        except Exception as e:
            self.add_notification_to_list(f"❌ Ошибка отправки сообщения: {e}")
    
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
        
        # Если кэш уже есть, просто обновляем позицию на последние сообщения
        if chat_id in self.cached_messages and len(self.cached_messages[chat_id]) > 0:
            self.scroll_position[chat_id] = max(0, len(self.cached_messages[chat_id]) - self.messages_per_page)
        else:
            # Загружаем сообщения и инициализируем кэш
            self.get_chat_messages(chat_id)
        return True
    
    def get_chat_messages(self, chat_id):
        try:
            request = messenger_pb2.GetMessagesRequest(chat_id=chat_id)
            response = self.stub.GetMessages(request)
            
            # Инициализируем кэш сообщений для скроллинга
            self.cached_messages[chat_id] = []
            
            # GetMessages возвращает сообщения в порядке desc (новые первыми)
            # Для скроллинга нужен порядок asc (старые первыми), поэтому реверсируем
            messages_list = []
            for msg in response.messages:
                created_at_dt = self.timestamp_to_datetime(msg.created_at)
                messages_list.append({
                    'id': msg.id,
                    'content': msg.content,
                    'nickname': msg.nickname,
                    'created_at': created_at_dt,
                    'timestamp': created_at_dt.strftime("%H:%M:%S")
                })
                self.get_user_color(msg.nickname)
            
            # Реверсируем для хранения в порядке asc (старые первыми)
            self.cached_messages[chat_id] = list(reversed(messages_list))
            
            # Инициализируем позицию скроллинга (показываем последние сообщения)
            self.scroll_position[chat_id] = max(0, len(self.cached_messages[chat_id]) - self.messages_per_page)
            self.scroll_scroll_id[chat_id] = None
            self.scroll_offset[chat_id] = len(self.cached_messages[chat_id])
                
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка получения сообщений: {e}")
    
    def load_more_messages(self, chat_id):
        """Загружает следующую порцию сообщений с сервера"""
        try:
            # Пробуем использовать scroll, если он активен
            if self.scroll_scroll_id.get(chat_id):
                try:
                    request = messenger_pb2.ScrollMessagesRequest(scroll_id=self.scroll_scroll_id[chat_id])
                    response = self.stub.ScrollMessages(request)
                    
                    if response.messages:
                        new_messages = []
                        for msg in response.messages:
                            created_at_dt = self.timestamp_to_datetime(msg.created_at)
                            new_messages.append({
                                'id': msg.id,
                                'content': msg.content,
                                'nickname': msg.nickname,
                                'created_at': created_at_dt,
                                'timestamp': created_at_dt.strftime("%H:%M:%S")
                            })
                            self.get_user_color(msg.nickname)
                        
                        # Добавляем в начало кэша (старые сообщения)
                        self.cached_messages[chat_id] = new_messages + self.cached_messages[chat_id]
                        self.scroll_scroll_id[chat_id] = response.scroll_id if response.scroll_id else None
                        self.scroll_offset[chat_id] = self.scroll_offset.get(chat_id, 0) + len(new_messages)
                        return True
                except grpc.RpcError:
                    # Scroll протух, используем search с offset
                    self.scroll_scroll_id[chat_id] = None
            
            # Используем search с offset для подгрузки
            request = messenger_pb2.SearchMessagesRequest(
                chat_id=chat_id,
                query="",
                tags=[],
                offset=self.scroll_offset.get(chat_id, 0)
            )
            response = self.stub.SearchMessages(request)
            
            if response.messages:
                new_messages = []
                for msg in response.messages:
                    created_at_dt = self.timestamp_to_datetime(msg.created_at)
                    new_messages.append({
                        'id': msg.id,
                        'content': msg.content,
                        'nickname': msg.nickname,
                        'created_at': created_at_dt,
                        'timestamp': created_at_dt.strftime("%H:%M:%S")
                    })
                    self.get_user_color(msg.nickname)
                
                # Добавляем в начало кэша (старые сообщения)
                self.cached_messages[chat_id] = new_messages + self.cached_messages[chat_id]
                self.scroll_scroll_id[chat_id] = response.scroll_id if response.scroll_id else None
                self.scroll_offset[chat_id] = self.scroll_offset.get(chat_id, 0) + len(new_messages)
                return True
            
            return False
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка загрузки сообщений: {e}")
            return False
    
    def scroll_up(self, chat_id):
        """Прокручивает вверх (показывает более старые сообщения)"""
        if chat_id not in self.cached_messages:
            return
        
        current_pos = self.scroll_position.get(chat_id, 0)
        
        # Если мы в начале кэша, пытаемся загрузить еще
        if current_pos == 0:
            if self.load_more_messages(chat_id):
                # После загрузки позиция остается 0, но кэш увеличился
                pass
            else:
                self.add_notification_to_list("📄 Больше старых сообщений нет")
                return
        
        # Прокручиваем вверх на messages_per_page
        new_pos = max(0, current_pos - self.messages_per_page)
        self.scroll_position[chat_id] = new_pos
        self.add_notification_to_list(f"⬆️ Прокрутка вверх (позиция {new_pos})")
    
    def scroll_down(self, chat_id):
        """Прокручивает вниз (показывает более новые сообщения)"""
        if chat_id not in self.cached_messages:
            return
        
        current_pos = self.scroll_position.get(chat_id, 0)
        total_messages = len(self.cached_messages[chat_id])
        
        # Прокручиваем вниз на messages_per_page
        new_pos = min(total_messages - self.messages_per_page, current_pos + self.messages_per_page)
        
        if new_pos == current_pos:
            self.add_notification_to_list("📄 Вы уже внизу")
            return
        
        self.scroll_position[chat_id] = new_pos
        self.add_notification_to_list(f"⬇️ Прокрутка вниз (позиция {new_pos})")
    
    def parse_search_query(self, query):
        """Парсит поисковый запрос, извлекая текст и теги"""
        import re
        # Находим все теги вида #tag, поддерживаем Unicode символы (русские буквы и др.)
        # Используем \w который в Python 3 поддерживает Unicode по умолчанию
        # Добавляем явную поддержку кириллицы и других Unicode букв
        tag_pattern = r'#([\w\u0400-\u04FF\u0500-\u052F]+)'  # \w + кириллица + расширенная кириллица
        tags = re.findall(tag_pattern, query)
        # Удаляем теги из текста запроса
        text_query = re.sub(tag_pattern, '', query).strip()
        return text_query, tags
    
    def search_messages(self, query):
        """Выполняет поиск сообщений по тексту и тегам"""
        try:
            text_query, tags = self.parse_search_query(query)
            request = messenger_pb2.SearchMessagesRequest(query=text_query, chat_id=self.current_chat_id, tags=tags, offset=0)
            response = self.stub.SearchMessages(request)
            
            self.search_results = []
            for msg in response.messages:
                created_at_dt = self.timestamp_to_datetime(msg.created_at)
                self.search_results.append({
                    'id': msg.id,
                    'content': msg.content,
                    'nickname': msg.nickname,
                    'chat_id': msg.chat_id,
                    'created_at': created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
                })
                self.get_user_color(msg.nickname)
            
            # Инициализируем позицию скроллинга (показываем первые результаты - самые новые)
            # При сортировке desc: индекс 0 = самое новое, индекс N = самое старое
            self.search_scroll_position = 0
            
            self.search_scroll_id = response.scroll_id if response.scroll_id else None
            
            if self.search_scroll_id:
                self.add_notification_to_list(f"✅ Найдено {len(self.search_results)} сообщений (показаны самые новые). Используйте /down для просмотра более старых сообщений")
            else:
                self.add_notification_to_list(f"✅ Найдено {len(self.search_results)} сообщений")
            
            return True
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка поиска: {e}")
            return False
    
    def scroll_search_results(self):
        """Загружает следующую пачку результатов поиска через scroll API
        
        Scroll API всегда загружает более старые результаты (при сортировке desc),
        поэтому результаты добавляются в конец списка.
        """
        if not self.search_scroll_id:
            self.add_notification_to_list("❌ Нет активного поиска или результаты закончились")
            return False
        
        try:
            request = messenger_pb2.ScrollMessagesRequest(scroll_id=self.search_scroll_id)
            response = self.stub.ScrollMessages(request)
            
            # Сохраняем новый scroll_id, даже если сообщений нет
            new_scroll_id = response.scroll_id if response.scroll_id else None
            
            if not response.messages:
                # Если нет сообщений и нет нового scroll_id, значит результаты закончились
                self.search_scroll_id = None
                self.add_notification_to_list("📄 Больше результатов нет")
                return False
            
            # Сохраняем ВСЕ сообщения из ответа
            new_results = []
            for msg in response.messages:
                created_at_dt = self.timestamp_to_datetime(msg.created_at)
                new_results.append({
                    'id': msg.id,
                    'content': msg.content,
                    'nickname': msg.nickname,
                    'chat_id': msg.chat_id,
                    'created_at': created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
                })
                self.get_user_color(msg.nickname)
            
            # Scroll API всегда загружает более старые результаты (при сортировке desc)
            # Добавляем их в конец списка
            self.search_results.extend(new_results)
            self.search_scroll_id = new_scroll_id
            
            self.add_notification_to_list(f"✅ Загружено еще {len(new_results)} сообщений (всего: {len(self.search_results)})")
            return True
        except grpc.RpcError as e:
            self.search_scroll_id = None
            self.add_notification_to_list(f"❌ Ошибка загрузки результатов: {e}")
            return False
    
    def get_chat_analytics(self):
        """Получает и отображает аналитику по чату"""
        try:
            request = messenger_pb2.GetChatAnalyticsRequest(chat_id=self.current_chat_id)
            response = self.stub.GetChatAnalytics(request)
            
            self.display_analytics(response)
            
        except grpc.RpcError as e:
            self.add_notification_to_list(f"❌ Ошибка получения аналитики: {e}")
        except Exception as e:
            self.add_notification_to_list(f"❌ Ошибка: {e}")
    
    def display_analytics(self, analytics):
        """Красиво отображает аналитику по чату"""
        chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
        
        print("\n" + "=" * 80)
        print(f"📊 АНАЛИТИКА ЧАТА: {chat_name}")
        print("=" * 80)
        
        # Общая статистика
        print("\n📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"  👥 Пользователей: {analytics.users_count}")
        print(f"  💬 Сообщений: {analytics.messages_count}")
        
        # Топ слов
        if analytics.words:
            print("\n🔤 ТОП СЛОВ:")
            max_words = min(10, len(analytics.words))
            for i, word_stat in enumerate(analytics.words[:max_words], 1):
                bar_length = min(30, int(word_stat.count * 30 / analytics.words[0].count)) if analytics.words else 0
                bar = "█" * bar_length
                print(f"  {i:2d}. {word_stat.word:20s} [{word_stat.count:5d}] {bar}")
        else:
            print("\n🔤 ТОП СЛОВ: Нет данных")
        
        # Топ тегов
        if analytics.tags:
            print("\n🏷️  ТОП ТЕГОВ:")
            max_tags = min(10, len(analytics.tags))
            for i, tag_stat in enumerate(analytics.tags[:max_tags], 1):
                bar_length = min(30, int(tag_stat.count * 30 / analytics.tags[0].count)) if analytics.tags else 0
                bar = "█" * bar_length
                tag_display = f"#{tag_stat.tag}" if not tag_stat.tag.startswith("#") else tag_stat.tag
                print(f"  {i:2d}. {tag_display:20s} [{tag_stat.count:5d}] {bar}")
        else:
            print("\n🏷️  ТОП ТЕГОВ: Нет данных")
        
        print("\n" + "=" * 80)
        input("\nНажмите Enter для продолжения...")
    
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
                    created_at_dt = self.timestamp_to_datetime(message.created_at)
                    # Добавляем новое сообщение в кэш для скроллинга
                    if message.chat_id not in self.cached_messages:
                        self.cached_messages[message.chat_id] = []
                    
                    cached = self.cached_messages[message.chat_id]
                    # Проверяем, не является ли это нашим оптимистично добавленным сообщением
                    # (смотрим по последнему сообщению с пустым ID и совпадающим контентом/никнеймом)
                    if cached and cached[-1].get('id') == '' and cached[-1]['content'] == message.content and cached[-1]['nickname'] == message.nickname:
                        # Заменяем временное сообщение на реальное с ID
                        cached[-1] = {
                            'id': message.id,
                            'content': message.content,
                            'nickname': message.nickname,
                            'created_at': created_at_dt,
                            'timestamp': created_at_dt.strftime("%H:%M:%S")
                        }
                    else:
                        # Добавляем новое сообщение
                        self.cached_messages[message.chat_id].append({
                            'id': message.id,
                            'content': message.content,
                            'nickname': message.nickname,
                            'created_at': created_at_dt,
                            'timestamp': created_at_dt.strftime("%H:%M:%S")
                        })
                        # Если мы внизу, обновляем позицию чтобы показать новое сообщение
                        scroll_pos = self.scroll_position.get(message.chat_id, 0)
                        total = len(self.cached_messages[message.chat_id])
                        if scroll_pos >= total - self.messages_per_page - 1:
                            self.scroll_position[message.chat_id] = max(0, total - self.messages_per_page)
                    
                    self.get_user_color(message.nickname)
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
                        created_at_dt = self.timestamp_to_datetime(message.created_at) if message.HasField('created_at') else datetime.now()
                        # Добавляем сообщение в кэш, если есть
                        if message.chat_id not in self.cached_messages:
                            self.cached_messages[message.chat_id] = []
                        self.cached_messages[message.chat_id].append({
                            'id': message.id if message.HasField('id') else '',
                            'content': message.content,
                            'nickname': message.nickname,
                            'created_at': created_at_dt,
                            'timestamp': created_at_dt.strftime("%H:%M:%S")
                        })
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
        
        if self.search_mode:
            print("🔍 РЕЖИМ ПОИСКА")
            print("=" * 40)
            if self.search_results:
                # Отображаем окно результатов с учетом позиции скроллинга
                start_idx = self.search_scroll_position
                end_idx = min(start_idx + self.messages_per_page, len(self.search_results))
                
                for i in range(start_idx, end_idx):
                    msg = self.search_results[i]
                    color = self.get_user_color(msg['nickname'])
                    chat_name = self.chat_names.get(msg['chat_id'], msg['chat_id'])
                    print(f"  \033[{color}m[{msg['created_at']}] {msg['nickname']} ({chat_name}): {msg['content']}\033[0m")
                
                # Показываем индикатор позиции
                if len(self.search_results) > self.messages_per_page:
                    print(f"\n  📍 Позиция: {start_idx}-{end_idx} из {len(self.search_results)} загружено", end="")
                    if self.search_scroll_id:
                        print(" (еще доступны)")
                    else:
                        print(" (все загружено)")
                    if self.search_scroll_position > 0:
                        print(f"  ⬆️ Используйте /up для просмотра более новых сообщений")
                    if end_idx < len(self.search_results) or self.search_scroll_id:
                        print(f"  ⬇️ Используйте /down для просмотра более старых сообщений")
            else:
                print("  Результаты поиска пусты")
            print()
            print("-" * 80)
            print("🔍 Введите запрос (текст и теги #tag) или команду (/up, /down, /exit_search): ", end="", flush=True)
        elif self.current_chat_id is None:
            print("🏠 ГЛАВНОЕ МЕНЮ")
            print("=" * 40)
            print("Доступные действия:")
            print("  /create <название> - создать чат")
            print("  /join <chat_id> - присоединиться к чату")
            print("  /chats - список ваших чатов")
            print("  /help - помощь")
            print("  /exit - выход")
            print()
            print("-" * 80)
            print("💬 Введите команду: ", end="", flush=True)
        else:
            chat_name = self.chat_names.get(self.current_chat_id, self.current_chat_id)
            print(f"💬 ЧАТ: {chat_name} ({self.current_chat_id})")
            print("=" * 40)
            
            # Отображаем сообщения из кэша с учетом позиции скроллинга
            if self.current_chat_id in self.cached_messages:
                cached = self.cached_messages[self.current_chat_id]
                scroll_pos = self.scroll_position.get(self.current_chat_id, max(0, len(cached) - self.messages_per_page))
                
                # Показываем окно сообщений
                start_idx = scroll_pos
                end_idx = min(start_idx + self.messages_per_page, len(cached))
                
                for i in range(start_idx, end_idx):
                    msg = cached[i]
                    color = self.get_user_color(msg['nickname'])
                    print(f"  \033[{color}m[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\033[0m")
                
                # Показываем индикатор позиции
                if len(cached) > self.messages_per_page:
                    print(f"\n  📍 Позиция: {start_idx}-{end_idx} из {len(cached)} сообщений")
                    if scroll_pos > 0:
                        print(f"  ⬆️ Используйте /up для просмотра старых сообщений")
                    if end_idx < len(cached):
                        print(f"  ⬇️ Используйте /down для просмотра новых сообщений")
            print()
            print("-" * 80)
            print(f"💬 Введите сообщение или команду (чат: {self.chat_names.get(self.current_chat_id, self.current_chat_id)}): ", end="", flush=True)
    
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def refresh_display(self):
        if self.current_chat_id:
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
        print("  /search            - войти в режим поиска по чату")
        print("  /analytics         - показать аналитику по чату")
        print("  /up                - прокрутить вверх (старые сообщения)")
        print("  /down              - прокрутить вниз (новые сообщения)")
        print()
        print("🔍 РЕЖИМ ПОИСКА:")
        print("  Введите запрос с текстом и тегами (#tag)")
        print("  /up                - прокрутить вверх (предыдущие результаты)")
        print("  /down              - прокрутить вниз (следующие результаты, автоматически загружает новые при необходимости)")
        print("  /exit_search       - выйти из режима поиска")
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
            print(f"  Всего сообщений: {len(self.cached_messages.get(self.current_chat_id, []))}")
            return
        elif command == "/analytics":
            if not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            self.get_chat_analytics()
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
        elif command == "/search":
            if not self.current_chat_id:
                print("❌ Вы не в чате. Сначала присоединитесь к чату через /join")
                return
            self.search_mode = True
            self.search_results = []
            self.search_scroll_id = None
            self.search_scroll_position = 0
            self.add_notification_to_list("🔍 Режим поиска активирован. Введите запрос с текстом и тегами (#tag)")
            return
        elif command == "/exit_search":
            self.search_mode = False
            self.search_results = []
            self.search_scroll_id = None
            self.search_scroll_position = 0
            self.add_notification_to_list("✅ Выход из режима поиска")
            return
        elif command == "/up":
            if self.search_mode:
                # Скроллинг вверх в результатах поиска (показываем более новые результаты)
                current_pos = self.search_scroll_position
                new_pos = max(0, current_pos - self.messages_per_page)
                if new_pos == current_pos:
                    # Если достигли начала загруженных результатов, больше новых результатов нет
                    # (scroll API не может загрузить более новые результаты, только более старые)
                    self.add_notification_to_list("📄 Вы уже в начале результатов (показаны самые новые сообщения)")
                else:
                    self.search_scroll_position = new_pos
                    self.add_notification_to_list(f"⬆️ Прокрутка вверх (позиция {new_pos})")
                self.refresh_display()
            elif not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            else:
                self.scroll_up(self.current_chat_id)
                self.refresh_display()
            return
        elif command == "/down":
            if self.search_mode:
                # Скроллинг вниз в результатах поиска
                current_pos = self.search_scroll_position
                total = len(self.search_results)
                
                # Проверяем, достигли ли мы конца загруженных результатов
                is_at_end = (current_pos + self.messages_per_page >= total)
                
                # Если достигли конца загруженных результатов и есть scroll_id, загружаем еще
                if is_at_end and self.search_scroll_id:
                    if self.scroll_search_results():
                        # После загрузки новых результатов обновляем позицию
                        total = len(self.search_results)
                        new_pos = min(total - self.messages_per_page, current_pos + self.messages_per_page)
                        if new_pos != current_pos:
                            self.search_scroll_position = new_pos
                            self.add_notification_to_list(f"⬇️ Прокрутка вниз (позиция {new_pos})")
                        else:
                            # Если после загрузки позиция не изменилась, значит загрузилось меньше чем messages_per_page
                            # Прокручиваем на то, что загрузилось
                            if total > current_pos:
                                self.search_scroll_position = max(0, total - self.messages_per_page)
                                self.add_notification_to_list(f"⬇️ Прокрутка вниз (позиция {self.search_scroll_position})")
                            else:
                                self.add_notification_to_list("📄 Больше результатов нет")
                    else:
                        # Scroll не удался, но может быть scroll_id еще есть (если просто нет результатов в этой порции)
                        if not self.search_scroll_id:
                            self.add_notification_to_list("📄 Больше результатов нет")
                        else:
                            self.add_notification_to_list("📄 Больше результатов в этой порции")
                elif is_at_end:
                    # Достигли конца и нет scroll_id
                    self.add_notification_to_list("📄 Вы уже в конце результатов")
                else:
                    # Прокручиваем вниз по уже загруженным результатам
                    new_pos = min(total - self.messages_per_page, current_pos + self.messages_per_page)
                    self.search_scroll_position = new_pos
                    self.add_notification_to_list(f"⬇️ Прокрутка вниз (позиция {new_pos})")
                self.refresh_display()
            elif not self.current_chat_id:
                print("❌ Вы не в чате")
                return
            else:
                self.scroll_down(self.current_chat_id)
                self.refresh_display()
            return
        else:
            if self.search_mode:
                # В режиме поиска обрабатываем запрос
                if user_input.strip():
                    self.search_messages(user_input)
            elif self.current_chat_id:
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
