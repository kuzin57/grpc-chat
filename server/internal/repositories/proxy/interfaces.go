package adapter

import (
	"context"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
)

type ChatRepository interface {
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
	SetTTLToChat(ctx context.Context, chatID string, ttl int32) error
	SearchMessages(ctx context.Context, chatID, query string, tags []string, offset int) ([]*entities.Message, string, error)
	ScrollMessages(ctx context.Context, scrollID string) ([]*entities.Message, string, error)
	GetUsersCount(ctx context.Context, chatID string) (int64, error)
	GetMessagesCount(ctx context.Context, chatID string) (int64, error)
	GetTopWords(ctx context.Context, chatID string, limit int) ([]entities.WordStat, error)
	GetTopTags(ctx context.Context, chatID string, limit int) ([]entities.TagStat, error)
}
