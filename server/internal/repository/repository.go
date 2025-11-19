package repository

import (
	"context"
	"log"
	"reflect"
	"time"

	"github.com/google/uuid"
	"github.com/kuzin57/grpc-chat/server/internal/config"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
	"github.com/redis/go-redis/v9"
)

const (
	scanChatUsersChunkSize = 100
	chatMessagesChunkSize  = 100
)

type Repository struct {
	redisClient *redis.Client
}

func NewRepository(config *config.Config) (*Repository, error) {
	redisClient := redis.NewClient(&redis.Options{
		Addr:     config.Redis.Host + ":" + config.Redis.Port,
		Password: config.Redis.Password,
		Username: config.Redis.User,
	})

	_, err := redisClient.Ping(context.Background()).Result()
	if err != nil {
		return nil, err
	}

	_, err = redisClient.Do(context.Background(), "CONFIG", "SET", "notify-keyspace-events", "KEA").Result()
	if err != nil {
		return nil, err
	}

	return &Repository{
		redisClient: redisClient,
	}, nil
}

func setStructToKey(ctx context.Context, redisClient *redis.Client, key string, value interface{}) error {
	val := reflect.ValueOf(value).Elem()

	settter := func(p redis.Pipeliner) error {
		for i := range val.NumField() {
			var (
				field = val.Type().Field(i)
				tag   = field.Tag.Get("redis")
			)

			if err := p.HSet(ctx, key, tag, val.Field(i).Interface()).Err(); err != nil {
				return err
			}
		}

		return nil
	}

	if _, err := redisClient.Pipelined(ctx, settter); err != nil {
		return err
	}

	return nil
}

func lookupByKeyPattern[T any](ctx context.Context, redisClient *redis.Client, pattern string) ([]*T, error) {
	var (
		allKeys []string
		cursor  uint64
	)

	for {
		keys, nextCursor, err := redisClient.Scan(ctx, cursor, pattern, scanChatUsersChunkSize).Result()
		if err != nil {
			return nil, err
		}

		allKeys = append(allKeys, keys...)
		cursor = nextCursor

		if cursor == 0 {
			break
		}
	}

	if len(allKeys) == 0 {
		return nil, nil
	}

	result := make([]*T, 0, len(allKeys))
	for _, key := range allKeys {
		var value T

		err := redisClient.HGetAll(ctx, key).Scan(&value)
		if err != nil {
			log.Println("Error getting value from key", key, "error", err)

			continue
		}

		result = append(result, &value)
	}

	return result, nil
}

func (r *Repository) GetChat(ctx context.Context, chatID string) (string, error) {
	var (
		chatKeys []string
		cursor   uint64
		err      error
	)

	for {
		chatKeys, cursor, err = r.redisClient.Scan(ctx, cursor, utils.BuildChatUserPatternByChat(chatID), 1).Result()
		if err != nil {
			return "", err
		}

		if cursor == 0 || len(chatKeys) > 0 {
			break
		}
	}

	if len(chatKeys) == 0 {
		return "", ErrChatNotFound
	}

	return utils.ExtractChatIDFromChatUserKey(chatKeys[0]), nil
}

func (r *Repository) CreateChat(ctx context.Context, chatID, nickname string) (string, error) {
	key := utils.BuildChatUserKey(chatID, nickname)

	if err := setStructToKey(ctx, r.redisClient, key, &entities.ChatUser{
		ChatID:   chatID,
		Nickname: nickname,
	}); err != nil {
		return "", err
	}

	return chatID, nil
}

func (r *Repository) AddUserToChat(ctx context.Context, chatID, nickname string) error {
	log.Println("Adding user to chat", chatID, "nickname", nickname)

	var (
		chatKeys []string
		cursor   uint64
		err      error
	)

	for {
		chatKeys, cursor, err = r.redisClient.Scan(ctx, cursor, utils.BuildChatUserPatternByChat(chatID), 1).Result()
		if err != nil {
			return err
		}

		if cursor == 0 {
			break
		}

		if len(chatKeys) > 0 {
			break
		}
	}

	if len(chatKeys) == 0 {
		return ErrChatNotFound
	}

	err = setStructToKey(ctx, r.redisClient, utils.BuildChatUserKey(chatID, nickname), &entities.ChatUser{
		ChatID:      chatID,
		Nickname:    nickname,
		NewMessages: 0,
	})
	if err != nil {
		return err
	}

	log.Println("Added user to chat", chatID, "nickname", nickname)

	return nil
}

func (r *Repository) RemoveUserFromChat(ctx context.Context, chatID, nickname string) error {
	_, err := r.redisClient.Del(ctx, utils.BuildChatUserKey(chatID, nickname)).Result()
	if err != nil {
		return err
	}

	return nil
}

func (r *Repository) GetUserChats(ctx context.Context, nickname string) ([]string, error) {
	chatKeys, _, err := r.redisClient.Scan(ctx, 0, utils.BuildChatUserPatternByUser(nickname), 100).Result()
	if err != nil {
		return nil, err
	}

	return utils.MapSlice(chatKeys, utils.ExtractChatIDFromChatUserKey), nil
}

func (r *Repository) GetChatsUsers(ctx context.Context, nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error) {
	keys := make(map[string]string)
	for _, chatID := range chatsIDs {
		keys[chatID] = utils.BuildChatUserKey(chatID, nickname)
	}

	result := make(map[string]*entities.ChatUser)

	for chatID, key := range keys {
		var chatUser entities.ChatUser

		err := r.redisClient.HGetAll(ctx, key).Scan(&chatUser)
		if err != nil {
			return nil, err
		}

		result[chatID] = &chatUser
	}

	return result, nil
}

func (r *Repository) CreateMessage(ctx context.Context, message entities.Message) (string, error) {
	message.ID = uuid.NewString()

	err := setStructToKey(ctx, r.redisClient, utils.BuildChatMessageKey(message.ChatID, message.ID), &message)
	if err != nil {
		return "", err
	}

	chatUsers, err := r.GetUsersByChatID(ctx, message.ChatID)
	if err != nil {
		return "", err
	}

	for _, user := range chatUsers {
		if user.Nickname != message.Nickname {
			user.NewMessages++

			err := setStructToKey(ctx, r.redisClient, utils.BuildChatUserKey(message.ChatID, user.Nickname), user)
			if err != nil {
				return "", err
			}
		}
	}

	return message.ID, nil
}

func (r *Repository) GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error) {
	return lookupByKeyPattern[entities.Message](ctx, r.redisClient, utils.BuildChatMessagePatternByChat(chatID))
}

func (r *Repository) SetMessagesRead(ctx context.Context, chatID, nickname string) error {
	chatUser := entities.ChatUser{
		ChatID:   chatID,
		Nickname: nickname,
	}

	err := setStructToKey(ctx, r.redisClient, utils.BuildChatUserKey(chatID, nickname), &chatUser)
	if err != nil {
		return err
	}

	return nil
}

func (r *Repository) GetUsersByChatID(ctx context.Context, chatID string) ([]*entities.ChatUser, error) {
	return lookupByKeyPattern[entities.ChatUser](ctx, r.redisClient, utils.BuildChatUserPatternByChat(chatID))
}

// TTL in minutes
func (r *Repository) SetTTLToChat(ctx context.Context, chatID string, ttl int32) error {
	var (
		messageKeys []string
		cursor      uint64
	)

	for {
		keys, nextCursor, err := r.redisClient.Scan(ctx, cursor, utils.BuildChatMessagePatternByChat(chatID), chatMessagesChunkSize).Result()
		if err != nil {
			return err
		}

		messageKeys = append(messageKeys, keys...)

		if cursor == 0 {
			break
		}

		cursor = nextCursor
	}

	if len(messageKeys) == 0 {
		return nil
	}

	for _, messageKey := range messageKeys {
		_, err := r.redisClient.Expire(ctx, messageKey, time.Duration(ttl)*time.Minute).Result()
		if err != nil {
			return err
		}
	}

	log.Println("Set TTL to chat", chatID, "ttl", ttl)

	return nil
}
