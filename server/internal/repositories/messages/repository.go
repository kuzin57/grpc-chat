package messages

import (
	"github.com/google/uuid"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
)

type Repository struct {
	receivedMessages map[string]*entities.Message
	sentMessages     map[string]*entities.Message
}

func NewRepository() *Repository {
	return &Repository{
		receivedMessages: make(map[string]*entities.Message),
		sentMessages:     make(map[string]*entities.Message),
	}
}

func (r *Repository) CreateMessage(message entities.Message) (string, error) {
	message.ID = uuid.NewString()
	r.receivedMessages[message.ToNickname] = &message
	r.sentMessages[message.FromNickname] = &message

	return message.ID, nil
}

func (r *Repository) GetReceivedMessages(nickname string) ([]*entities.Message, error) {
	var messages []*entities.Message
	for _, message := range r.receivedMessages {
		if message.ToNickname == nickname {
			messages = append(messages, message)
		}
	}

	return messages, nil
}

func (r *Repository) GetSentMessages(nickname string) ([]*entities.Message, error) {
	var messages []*entities.Message
	for _, message := range r.sentMessages {
		if message.FromNickname == nickname {
			messages = append(messages, message)
		}
	}

	return messages, nil
}
