package server

import (
	"context"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/generated"
)

type MessagesService interface {
	SendMessage(ctx context.Context, text, fromNickname, toNickname string) (string, error)
	GetReceivedMessages(ctx context.Context, nickname string) ([]*entities.Message, error)
	GetSentMessages(ctx context.Context, nickname string) ([]*entities.Message, error)
}

type MessengerServer interface {
	SendMessage(context.Context, *generated.SendMessageRequest) (*generated.SendMessageResponse, error)
	GetReceivedMessages(context.Context, *generated.GetReceivedMessagesRequest) (*generated.GetReceivedMessagesResponse, error)
	GetSentMessages(context.Context, *generated.GetSentMessagesRequest) (*generated.GetSentMessagesResponse, error)
}
