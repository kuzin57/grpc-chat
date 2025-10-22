package repository

import (
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
)

type Repository struct {
	mu           *sync.RWMutex
	chats        map[string]*entities.Chat
	chatUsers    map[string][]*entities.ChatUser
	usersToChats map[string][]*entities.Chat
	messages     map[string][]*entities.Message
}

func NewRepository() *Repository {
	return &Repository{
		mu:           &sync.RWMutex{},
		chats:        make(map[string]*entities.Chat),
		chatUsers:    make(map[string][]*entities.ChatUser),
		usersToChats: make(map[string][]*entities.Chat),
		messages:     make(map[string][]*entities.Message),
	}
}

func (r *Repository) GetChat(chatID string) (*entities.Chat, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	chat, ok := r.chats[chatID]
	if !ok {
		return nil, ErrChatNotFound
	}

	return chat, nil
}

func (r *Repository) CreateChat(chat entities.Chat, nickname string) (string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	log.Println("chat", chat, "nickname", nickname)

	r.chats[chat.ID] = &chat

	r.chatUsers[chat.ID] = append(r.chatUsers[chat.ID], &entities.ChatUser{
		ChatID:   chat.ID,
		Nickname: nickname,
		JoinedAt: time.Now(),
	})
	r.usersToChats[nickname] = append(r.usersToChats[nickname], &chat)

	log.Println("chatUsers", r.chatUsers, "usersToChats", r.usersToChats)

	return chat.ID, nil
}

func (r *Repository) AddUserToChat(chatID, nickname string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	log.Println("Adding user to chat", chatID, "nickname", nickname)

	chat, ok := r.chats[chatID]
	if !ok {
		return ErrChatNotFound
	}

	r.chatUsers[chatID] = append(r.chatUsers[chatID], &entities.ChatUser{
		ChatID:   chatID,
		Nickname: nickname,
		JoinedAt: time.Now(),
	})
	r.usersToChats[nickname] = append(r.usersToChats[nickname], chat)

	return nil
}

func (r *Repository) RemoveUserFromChat(chatID, nickname string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.chatUsers[chatID] = utils.FilterSlice(r.chatUsers[chatID], func(user *entities.ChatUser) bool {
		return user.Nickname != nickname
	})
	r.usersToChats[nickname] = utils.FilterSlice(r.usersToChats[nickname], func(chat *entities.Chat) bool {
		return chat.ID != chatID
	})

	if len(r.chatUsers[chatID]) == 0 {
		delete(r.chats, chatID)
		delete(r.chatUsers, chatID)
	}

	return nil
}

func (r *Repository) GetUserChats(nickname string) ([]*entities.Chat, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return r.usersToChats[nickname], nil
}

func (r *Repository) GetChatUsers(nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	chatUsers := make(map[string]*entities.ChatUser)
	for _, chatID := range chatsIDs {
		for _, user := range r.chatUsers[chatID] {
			if user.Nickname == nickname {
				chatUsers[chatID] = user
			}
		}
	}

	return chatUsers, nil
}

func (r *Repository) CreateMessage(message entities.Message) (string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	message.ID = uuid.NewString()
	r.messages[message.ChatID] = append(r.messages[message.ChatID], &message)

	for _, user := range r.chatUsers[message.ChatID] {
		if user.Nickname != message.Nickname {
			user.NewMessages++
		}
	}

	return message.ID, nil
}

func (r *Repository) GetMessages(chatID string) ([]*entities.Message, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return r.messages[chatID], nil
}

func (r *Repository) SetMessagesRead(chatID, nickname string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	for _, user := range r.chatUsers[chatID] {
		if user.Nickname != nickname {
			user.NewMessages = 0
		}
	}

	return nil
}
