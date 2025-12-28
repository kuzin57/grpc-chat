package adapter

import (
	"context"
	"fmt"

	"github.com/kuzin57/grpc-chat/server/internal/config"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
	searchRepo "github.com/kuzin57/grpc-chat/server/internal/repositories/opensearch"
	cacheRepo "github.com/kuzin57/grpc-chat/server/internal/repositories/redis"
)

type Repository struct {
	next ChatRepository
}

func NewRepository(cfg *config.Config) (*Repository, error) {
	var (
		err  error
		next ChatRepository
	)

	if cfg.UseOpensearch {
		next, err = searchRepo.NewRepository(cfg)
	} else {
		next, err = cacheRepo.NewRepository(cfg)
	}

	if err != nil {
		return nil, fmt.Errorf("init repository: %w", err)
	}

	return &Repository{next: next}, nil
}

func (r *Repository) CreateMessage(ctx context.Context, message entities.Message) (string, error) {
	return r.next.CreateMessage(ctx, message)
}

func (r *Repository) GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error) {
	return r.next.GetMessages(ctx, chatID)
}

func (r *Repository) CreateChat(ctx context.Context, chatID, nickname string) (string, error) {
	return r.next.CreateChat(ctx, chatID, nickname)
}

func (r *Repository) AddUserToChat(ctx context.Context, chatID, nickname string) error {
	return r.next.AddUserToChat(ctx, chatID, nickname)
}

func (r *Repository) RemoveUserFromChat(ctx context.Context, chatID, nickname string) error {
	return r.next.RemoveUserFromChat(ctx, chatID, nickname)
}

func (r *Repository) GetChat(ctx context.Context, chatID string) (string, error) {
	return r.next.GetChat(ctx, chatID)
}

func (r *Repository) GetUserChats(ctx context.Context, nickname string) ([]string, error) {
	return r.next.GetUserChats(ctx, nickname)
}

func (r *Repository) SetMessagesRead(ctx context.Context, chatID, nickname string) error {
	return r.next.SetMessagesRead(ctx, chatID, nickname)
}

func (r *Repository) GetChatsUsers(ctx context.Context, nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error) {
	return r.next.GetChatsUsers(ctx, nickname, chatsIDs)
}

func (r *Repository) GetUsersByChatID(ctx context.Context, chatID string) ([]*entities.ChatUser, error) {
	return r.next.GetUsersByChatID(ctx, chatID)
}

func (r *Repository) SetTTLToChat(ctx context.Context, chatID string, ttl int32) error {
	return r.next.SetTTLToChat(ctx, chatID, ttl)
}

func (r *Repository) SearchMessages(ctx context.Context, chatID, query string, tags []string, offset int) ([]*entities.Message, string, error) {
	return r.next.SearchMessages(ctx, chatID, query, tags, offset)
}

func (r *Repository) ScrollMessages(ctx context.Context, scrollID string) ([]*entities.Message, string, error) {
	return r.next.ScrollMessages(ctx, scrollID)
}

func (r *Repository) GetUsersCount(ctx context.Context, chatID string) (int64, error) {
	return r.next.GetUsersCount(ctx, chatID)
}

func (r *Repository) GetMessagesCount(ctx context.Context, chatID string) (int64, error) {
	return r.next.GetMessagesCount(ctx, chatID)
}

func (r *Repository) GetTopWords(ctx context.Context, chatID string, limit int) ([]entities.WordStat, error) {
	return r.next.GetTopWords(ctx, chatID, limit)
}

func (r *Repository) GetTopTags(ctx context.Context, chatID string, limit int) ([]entities.TagStat, error) {
	return r.next.GetTopTags(ctx, chatID, limit)
}
