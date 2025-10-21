package messages

import (
	"context"
	"log"
	"time"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/repositories/messages"
)

type Service struct {
	messageRepo *messages.Repository
}

func NewService(messageRepo *messages.Repository) *Service {
	return &Service{
		messageRepo: messageRepo,
	}
}

func (s *Service) SendMessage(ctx context.Context, text, fromNickname, toNickname string) (string, error) {
	message := entities.Message{
		Content:      text,
		FromNickname: fromNickname,
		ToNickname:   toNickname,
		CreatedAt:    time.Now(),
	}

	log.Println("Sending message:", text, "from", fromNickname, "to", toNickname)

	messageID, err := s.messageRepo.CreateMessage(message)
	if err != nil {
		return "", err
	}

	return messageID, nil
}

func (s *Service) GetReceivedMessages(ctx context.Context, nickname string) ([]*entities.Message, error) {
	log.Println("Getting received messages for", nickname)
	return s.messageRepo.GetReceivedMessages(nickname)
}

func (s *Service) GetSentMessages(ctx context.Context, nickname string) ([]*entities.Message, error) {
	log.Println("Getting sent messages for", nickname)
	return s.messageRepo.GetSentMessages(nickname)
}
