package messenger

import (
	"context"
	"errors"
	"fmt"
	"log"
	"regexp"
	"sync"
	"time"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/generated"
	"github.com/kuzin57/grpc-chat/server/internal/repositories"
	"golang.org/x/sync/errgroup"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const (
	topWordsLimit = 10
	topTagsLimit  = 10
)

type Service struct {
	repo Repository
}

func NewService(repo Repository) *Service {
	return &Service{
		repo: repo,
	}
}

func (s *Service) extractTags(text string) []string {
	re := regexp.MustCompile(`#([\p{L}\p{N}_]+)`)

	matches := re.FindAllStringSubmatch(text, -1)
	tags := make([]string, 0, len(matches))
	for _, match := range matches {
		if len(match) > 1 {
			tags = append(tags, match[1])
		}
	}

	return tags
}

func (s *Service) SendMessage(ctx context.Context, text, nickname, chatID string) (entities.Message, error) {
	_, err := s.repo.GetChat(ctx, chatID)
	if err != nil {
		return entities.Message{}, err
	}

	log.Println("Sending message:", text, "tags", s.extractTags(text))

	message := entities.Message{
		Content:   text,
		ChatID:    chatID,
		Nickname:  nickname,
		CreatedAt: time.Now(),
		Tags:      s.extractTags(text),
	}

	log.Println("Sending message:", text, "chat", chatID)

	messageID, err := s.repo.CreateMessage(ctx, message)
	if err != nil {
		return entities.Message{}, err
	}

	message.ID = messageID

	return message, nil
}

func (s *Service) GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error) {
	_, err := s.repo.GetChat(ctx, chatID)
	if err != nil {
		return nil, err
	}

	log.Println("Getting messages for", chatID)
	return s.repo.GetMessages(ctx, chatID)
}

func (s *Service) GetUserChats(ctx context.Context, nickname string) ([]string, map[string]*entities.ChatUser, error) {
	chats, err := s.repo.GetUserChats(ctx, nickname)
	if err != nil {
		return nil, nil, err
	}

	log.Println("Getting chat users for", nickname, "chats", chats)

	chatUsers, err := s.repo.GetChatsUsers(ctx, nickname, chats)
	if err != nil {
		return nil, nil, err
	}

	return chats, chatUsers, nil
}

func (s *Service) SetMessagesRead(ctx context.Context, chatID, nickname string) error {
	return s.repo.SetMessagesRead(ctx, chatID, nickname)
}

func (s *Service) CreateChat(ctx context.Context, name, nickname string) (string, error) {
	existingChat, err := s.repo.GetChat(ctx, name)
	if err != nil && !errors.Is(err, repositories.ErrChatNotFound) {
		return "", err
	}

	if existingChat != "" {
		return "", ErrChatAlreadyExists
	}

	return s.repo.CreateChat(ctx, name, nickname)
}

func (s *Service) AddUserToChat(ctx context.Context, chatID, nickname string) error {
	return s.repo.AddUserToChat(ctx, chatID, nickname)
}

func (s *Service) RemoveUserFromChat(ctx context.Context, chatID, nickname string) error {
	return s.repo.RemoveUserFromChat(ctx, chatID, nickname)
}

func (s *Service) Broadcast(
	ctx context.Context,
	message entities.Message,
	messageType generated.ChatMessageType,
	streams map[string]generated.Messenger_ChatStreamServer,
	mu *sync.RWMutex,
) error {
	users, err := s.repo.GetUsersByChatID(ctx, message.ChatID)
	if err != nil {
		return err
	}

	var wg sync.WaitGroup
	errorChan := make(chan error, len(users))

	for _, user := range users {
		if user.Nickname == message.Nickname {
			continue
		}

		wg.Add(1)
		go func(userNickname string) {
			defer wg.Done()

			mu.RLock()
			stream, ok := streams[userNickname]
			mu.RUnlock()

			if !ok {
				return
			}

			log.Println("Sending message to user", userNickname, "message", message)

			sendCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()

			select {
			case <-sendCtx.Done():
				log.Printf("Send context cancelled for user %s", userNickname)
				errorChan <- sendCtx.Err()
				return
			default:
				err := stream.Send(&generated.ChatMessage{
					Id:        message.ID,
					Content:   message.Content,
					Nickname:  message.Nickname,
					ChatId:    message.ChatID,
					CreatedAt: timestamppb.New(message.CreatedAt),
					Type:      messageType,
				})
				if err != nil {
					log.Printf("Failed to send message to user %s: %v", userNickname, err)

					if err.Error() == "rpc error: code = Canceled desc = context canceled" ||
						err.Error() == "rpc error: code = Unavailable desc = transport is closing" ||
						err.Error() == "rpc error: code = DeadlineExceeded desc = context deadline exceeded" {
						log.Printf("Removing closed stream for user %s", userNickname)
						mu.Lock()
						delete(streams, userNickname)
						mu.Unlock()
					} else {
						log.Printf("Temporary error for user %s, keeping stream: %v", userNickname, err)
					}
					errorChan <- err
				} else {
					errorChan <- nil
				}
			}
		}(user.Nickname)
	}

	wg.Wait()
	close(errorChan)

	hasErrors := false
	for err := range errorChan {
		if err != nil {
			hasErrors = true
		}
	}

	if hasErrors {
		log.Printf("Broadcast completed with some errors for chat %s", message.ChatID)
	}

	return nil
}

func (s *Service) SetTTLToChat(ctx context.Context, chatID string, ttl int32) error {
	return s.repo.SetTTLToChat(ctx, chatID, ttl)
}

func (s *Service) SearchMessages(ctx context.Context, chatID, query string, tags []string, offset int) ([]*entities.Message, string, error) {
	return s.repo.SearchMessages(ctx, chatID, query, tags, offset)
}

func (s *Service) ScrollMessages(ctx context.Context, scrollID string) ([]*entities.Message, string, error) {
	return s.repo.ScrollMessages(ctx, scrollID)
}

func (s *Service) GetChatStats(ctx context.Context, chatID string) (stats entities.ChatStats, err error) {
	errGroup := errgroup.Group{}

	errGroup.Go(func() error {
		usersCount, err := s.repo.GetUsersCount(ctx, chatID)
		if err != nil {
			return err
		}
		stats.UsersCount = usersCount
		return nil
	})

	errGroup.Go(func() error {
		messagesCount, err := s.repo.GetMessagesCount(ctx, chatID)
		if err != nil {
			return err
		}
		stats.MessagesCount = messagesCount
		return nil
	})

	errGroup.Go(func() error {
		words, err := s.repo.GetTopWords(ctx, chatID, topWordsLimit)
		if err != nil {
			return err
		}
		stats.Words = words
		return nil
	})

	errGroup.Go(func() error {
		tags, err := s.repo.GetTopTags(ctx, chatID, topTagsLimit)
		if err != nil {
			return err
		}
		stats.Tags = tags
		return nil
	})

	err = errGroup.Wait()
	if err != nil {
		return entities.ChatStats{}, fmt.Errorf("get chat stats: %w", err)
	}

	return stats, nil
}
