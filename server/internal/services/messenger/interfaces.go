package messenger

import (
	"context"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
)

type Repository interface {
	CreateMessage(ctx context.Context, message entities.Message) (string, error)
	GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error)
	CreateChat(ctx context.Context, chatID, nickname string) (string, error)
	AddUserToChat(ctx context.Context, chatID, nickname string) error
	RemoveUserFromChat(ctx context.Context, chatID, nickname string) error
	GetChat(ctx context.Context, chatID string) (string, error)
	GetUserChats(ctx context.Context, nickname string) ([]string, error)
	SetMessagesRead(ctx context.Context, chatID, nickname string) error
	GetChatsUsers(ctx context.Context, nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error)
	GetUsersByChatID(ctx context.Context, chatID string) ([]*entities.ChatUser, error)
}
