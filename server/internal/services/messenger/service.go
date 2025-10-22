package messenger

import (
	"context"
	"errors"
	"log"
	"time"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/repository"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
)

type Service struct {
	repo Repository
}

func NewService(repo Repository) *Service {
	return &Service{
		repo: repo,
	}
}

func (s *Service) SendMessage(ctx context.Context, text, nickname, chatID string) (string, error) {
	_, err := s.repo.GetChat(chatID)
	if err != nil {
		return "", err
	}

	message := entities.Message{
		Content:   text,
		ChatID:    chatID,
		Nickname:  nickname,
		CreatedAt: time.Now(),
	}

	log.Println("Sending message:", text, "chat", chatID)

	messageID, err := s.repo.CreateMessage(message)
	if err != nil {
		return "", err
	}

	return messageID, nil
}

func (s *Service) GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error) {
	_, err := s.repo.GetChat(chatID)
	if err != nil {
		return nil, err
	}

	log.Println("Getting messages for", chatID)
	return s.repo.GetMessages(chatID)
}

func (s *Service) GetUserChats(ctx context.Context, nickname string) ([]*entities.Chat, map[string]*entities.ChatUser, error) {
	chats, err := s.repo.GetUserChats(nickname)
	if err != nil {
		return nil, nil, err
	}

	log.Println("Getting chat users for", nickname, "chats", utils.MapSlice(chats, func(chat *entities.Chat) string { return chat.ID }))

	chatUsers, err := s.repo.GetChatUsers(nickname, utils.MapSlice(chats, func(chat *entities.Chat) string { return chat.ID }))
	if err != nil {
		return nil, nil, err
	}

	return chats, chatUsers, nil
}

func (s *Service) SetMessagesRead(ctx context.Context, chatID, nickname string) error {
	return s.repo.SetMessagesRead(chatID, nickname)
}

func (s *Service) CreateChat(ctx context.Context, name, nickname string) (string, error) {
	existingChat, err := s.repo.GetChat(name)
	if err != nil && !errors.Is(err, repository.ErrChatNotFound) {
		return "", err
	}

	if existingChat != nil {
		return "", ErrChatAlreadyExists
	}

	chat := entities.Chat{
		ID:        name,
		CreatedAt: time.Now(),
	}

	return s.repo.CreateChat(chat, nickname)
}

func (s *Service) AddUserToChat(ctx context.Context, chatID, nickname string) error {
	return s.repo.AddUserToChat(chatID, nickname)
}

func (s *Service) RemoveUserFromChat(ctx context.Context, chatID, nickname string) error {
	return s.repo.RemoveUserFromChat(chatID, nickname)
}
