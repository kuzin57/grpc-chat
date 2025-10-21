package messages

import (
	"github.com/google/uuid"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
)

type Repository struct {
	receivedMessages map[string][]*entities.Message
	sentMessages     map[string][]*entities.Message
}

func NewRepository() *Repository {
	return &Repository{
		receivedMessages: make(map[string][]*entities.Message),
		sentMessages:     make(map[string][]*entities.Message),
	}
}

func (r *Repository) CreateMessage(message entities.Message) (string, error) {
	message.ID = uuid.NewString()
	r.receivedMessages[message.ToNickname] = append(r.receivedMessages[message.ToNickname], &message)
	r.sentMessages[message.FromNickname] = append(r.sentMessages[message.FromNickname], &message)

	return message.ID, nil
}

func (r *Repository) GetReceivedMessages(nickname string) ([]*entities.Message, error) {
	return r.receivedMessages[nickname], nil
}

func (r *Repository) GetSentMessages(nickname string) ([]*entities.Message, error) {
	return r.sentMessages[nickname], nil
}
