package server

import (
	"context"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/generated"
)

type MessengerService interface {
	SendMessage(ctx context.Context, text, nickname, chatID string) (string, error)
	GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error)
	GetUserChats(ctx context.Context, nickname string) ([]*entities.Chat, map[string]*entities.ChatUser, error)
	CreateChat(ctx context.Context, name, nickname string) (string, error)
	AddUserToChat(ctx context.Context, chatID, nickname string) error
	RemoveUserFromChat(ctx context.Context, chatID, nickname string) error
	SetMessagesRead(ctx context.Context, chatID, nickname string) error
}

type MessengerServer interface {
	SendMessage(context.Context, *generated.SendMessageRequest) (*generated.SendMessageResponse, error)
	GetMessages(context.Context, *generated.GetMessagesRequest) (*generated.GetMessagesResponse, error)
	GetUserChats(context.Context, *generated.GetUserChatsRequest) (*generated.GetUserChatsResponse, error)
	CreateChat(context.Context, *generated.CreateChatRequest) (*generated.CreateChatResponse, error)
	LeaveChat(context.Context, *generated.LeaveChatRequest) (*generated.LeaveChatResponse, error)
	JoinChat(context.Context, *generated.JoinChatRequest) (*generated.JoinChatResponse, error)
}
