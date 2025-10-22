#!/usr/bin/env python3

import curses
import sys
import threading
import time
from datetime import datetime
from generated import messenger_pb2
from generated import messenger_pb2_grpc
import grpc


class ConsoleChat:
    def __init__(self, server_address='localhost:8080'):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.nickname = None
        self.messages = []
        self.input_buffer = ""
        self.running = False
        self.last_message_time = time.time()
        
        # Настройки экрана
        self.messages_height = 0
        self.input_height = 3
        
    def connect(self):
        """Подключение к серверу"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = messenger_pb2_grpc.MessengerStub(self.channel)
            return True
        except Exception as e:
            return False
    
    def disconnect(self):
        """Отключение от сервера"""
        if self.channel:
            self.channel.close()
    
    def send_message(self, message, to_nickname):
        """Отправка сообщения"""
        try:
            request = messenger_pb2.SendMessageRequest(
                message=message,
                from_nickname=self.nickname,
                to_nickname=to_nickname
            )
            
            response = self.stub.SendMessage(request)
            # Добавляем отправленное сообщение в локальный список
            self.add_message(f"[{self.nickname}] -> [{to_nickname}]: {message}", "sent")
            return response.message_id
        except grpc.RpcError as e:
            self.add_message(f"❌ Ошибка отправки: {e}", "error")
            return None
    
    def get_received_messages(self):
        """Получение новых сообщений"""
        try:
            request = messenger_pb2.GetReceivedMessagesRequest(nickname=self.nickname)
            response = self.stub.GetReceivedMessages(request)
            
            for msg in response.messages:
                # Проверяем, не показывали ли мы уже это сообщение
                msg_time = datetime.fromisoformat(msg.created_at.replace('Z', '+00:00'))
                if msg_time.timestamp() > self.last_message_time:
                    self.add_message(f"[{msg.from_nickname}]: {msg.content}", "received")
            
            self.last_message_time = time.time()
            return response.messages
        except grpc.RpcError as e:
            self.add_message(f"❌ Ошибка получения сообщений: {e}", "error")
            return []
    
    def add_message(self, message, msg_type="info"):
        """Добавление сообщения в список"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.messages.append((formatted_message, msg_type))
        
        # Ограничиваем количество сообщений для производительности
        if len(self.messages) > 1000:
            self.messages = self.messages[-500:]
    
    def init_screen(self):
        """Инициализация экрана curses"""
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        curses.curs_set(1)
        
        # Получаем размеры экрана
        self.height, self.width = self.stdscr.getmaxyx()
        self.messages_height = self.height - self.input_height
        
        # Создаем окна
        self.messages_win = curses.newwin(self.messages_height, self.width, 0, 0)
        self.input_win = curses.newwin(self.input_height, self.width, self.messages_height, 0)
        
        # Настраиваем прокрутку для окна сообщений
        self.messages_win.scrollok(True)
        self.messages_win.idlok(True)
        
        # Настраиваем прокрутку для окна ввода
        self.input_win.scrollok(True)
        
        # Добавляем заголовки
        self.draw_headers()
    
    def draw_headers(self):
        """Отрисовка заголовков окон"""
        # Заголовок области сообщений
        self.messages_win.addstr(0, 0, "=" * self.width, curses.A_REVERSE)
        self.messages_win.addstr(0, 2, "📨 СООБЩЕНИЯ", curses.A_REVERSE | curses.A_BOLD)
        
        # Заголовок области ввода
        self.input_win.addstr(0, 0, "=" * self.width, curses.A_REVERSE)
        self.input_win.addstr(0, 2, "✏️  ВВОД", curses.A_REVERSE | curses.A_BOLD)
        self.input_win.addstr(1, 0, f"{self.nickname} >> ", curses.A_BOLD)
    
    def draw_messages(self):
        """Отрисовка сообщений"""
        self.messages_win.clear()
        self.draw_headers()
        
        # Показываем последние сообщения, которые помещаются на экране
        start_line = max(0, len(self.messages) - (self.messages_height - 2))
        
        for i, (message, msg_type) in enumerate(self.messages[start_line:]):
            line = i + 1
            if line >= self.messages_height - 1:
                break
                
            # Выбираем цвет в зависимости от типа сообщения
            color = curses.A_NORMAL
            if msg_type == "received":
                color = curses.color_pair(2) | curses.A_BOLD  # Зеленый для полученных
            elif msg_type == "sent":
                color = curses.color_pair(3) | curses.A_BOLD  # Синий для отправленных
            elif msg_type == "error":
                color = curses.color_pair(1) | curses.A_BOLD  # Красный для ошибок
            
            # Обрезаем сообщение если оно слишком длинное
            display_message = message[:self.width-1]
            self.messages_win.addstr(line, 1, display_message, color)
        
        self.messages_win.refresh()
    
    def draw_input(self):
        """Отрисовка области ввода"""
        self.input_win.clear()
        self.draw_headers()
        
        # Показываем текущий буфер ввода
        prompt = f"{self.nickname} >> "
        self.input_win.addstr(1, 0, prompt, curses.A_BOLD)
        self.input_win.addstr(1, len(prompt), self.input_buffer)
        
        # Показываем подсказки
        self.input_win.addstr(2, 0, "Команды: /help - справка, /exit - выход, /to <ник> - выбрать получателя")
        
        self.input_win.refresh()
    
    def handle_input(self, key):
        """Обработка ввода пользователя"""
        if key == curses.KEY_BACKSPACE or key == 127:
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
        elif key == 10 or key == 13:  # Enter
            self.process_command(self.input_buffer.strip())
            self.input_buffer = ""
        elif 32 <= key <= 126:  # Печатные символы
            self.input_buffer += chr(key)
        
        self.draw_input()
    
    def process_command(self, command):
        """Обработка команд"""
        if not command:
            return
        
        if command == "/exit":
            self.running = False
        elif command == "/help":
            help_messages = [
                "/help - показать эту справку",
                "/exit - выйти из чата",
                "/to <никнейм> - отправить сообщение конкретному пользователю",
                "/refresh - обновить сообщения",
                "или просто введите сообщение для отправки всем"
            ]
            for msg in help_messages:
                self.add_message(msg, "info")
        elif command.startswith("/to "):
            # Команда для отправки сообщения конкретному пользователю
            parts = command.split(" ", 2)
            if len(parts) >= 3:
                to_nickname = parts[1]
                message = parts[2]
                self.send_message(message, to_nickname)
            else:
                self.add_message("Использование: /to <никнейм> <сообщение>", "error")
        elif command == "/refresh":
            self.get_received_messages()
        else:
            # Обычное сообщение - отправляем всем (можно изменить логику)
            self.add_message(f"Для отправки сообщения используйте: /to <никнейм> <сообщение>", "info")
    
    def message_polling_thread(self):
        """Поток для периодического получения новых сообщений"""
        while self.running:
            try:
                self.get_received_messages()
                time.sleep(2)  # Проверяем новые сообщения каждые 2 секунды
            except Exception as e:
                self.add_message(f"❌ Ошибка в потоке опроса: {e}", "error")
                time.sleep(5)
    
    def run(self):
        """Основной цикл приложения"""
        # Инициализируем экран
        self.init_screen()
        
        # Настраиваем цвета
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)      # Ошибки
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)    # Полученные сообщения
        curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)     # Отправленные сообщения
        
        self.running = True
        
        # Запускаем поток для получения сообщений
        polling_thread = threading.Thread(target=self.message_polling_thread, daemon=True)
        polling_thread.start()
        
        # Добавляем приветственное сообщение
        self.add_message(f"Добро пожаловать в консольный чат, {self.nickname}!", "info")
        self.add_message("Введите /help для получения справки", "info")
        
        # Основной цикл
        while self.running:
            try:
                self.draw_messages()
                self.draw_input()
                
                key = self.stdscr.getch()
                self.handle_input(key)
                
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.add_message(f"❌ Ошибка: {e}", "error")
        
        # Завершение
        self.disconnect()
        curses.endwin()


def main():
    if len(sys.argv) < 2:
        print("Использование: python console_chat.py <server_address>")
        print("Пример: python console_chat.py localhost:8080")
        sys.exit(1)
    
    server_address = sys.argv[1]
    
    # Получаем никнейм пользователя
    nickname = input("Введите ваше имя: ").strip()
    if not nickname:
        print("Никнейм не может быть пустым!")
        sys.exit(1)
    
    # Создаем и запускаем чат
    chat = ConsoleChat(server_address)
    chat.nickname = nickname
    
    if not chat.connect():
        print(f"❌ Не удалось подключиться к серверу {server_address}")
        sys.exit(1)
    
    try:
        chat.run()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        curses.endwin()
    finally:
        print("👋 До свидания!")


if __name__ == "__main__":
    main()
