package messenger

import "github.com/kuzin57/grpc-chat/server/internal/entities"

type Repository interface {
	CreateMessage(message entities.Message) (string, error)
	GetMessages(chatID string) ([]*entities.Message, error)
	CreateChat(chat entities.Chat, nickname string) (string, error)
	AddUserToChat(chatID, nickname string) error
	RemoveUserFromChat(chatID, nickname string) error
	GetChat(chatID string) (*entities.Chat, error)
	GetUserChats(nickname string) ([]*entities.Chat, error)
	SetMessagesRead(chatID, nickname string) error
	GetChatUsers(nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error)
}
