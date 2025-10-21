package server

import (
	"context"
	"time"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/generated"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
)

var (
	_ generated.MessengerServer = (*Server)(nil)
	_ MessengerServer           = (*Server)(nil)
)

type Server struct {
	generated.UnimplementedMessengerServer
	messagesService MessagesService
}

func NewServer(messagesService MessagesService) *Server {
	return &Server{
		messagesService: messagesService,
	}
}

func (s *Server) SendMessage(ctx context.Context, req *generated.SendMessageRequest) (*generated.SendMessageResponse, error) {
	messageID, err := s.messagesService.SendMessage(ctx, req.Message, req.FromNickname, req.ToNickname)
	if err != nil {
		return nil, err
	}

	return &generated.SendMessageResponse{
		MessageId: messageID,
	}, nil
}

func (s *Server) GetReceivedMessages(ctx context.Context, req *generated.GetReceivedMessagesRequest) (*generated.GetReceivedMessagesResponse, error) {
	messages, err := s.messagesService.GetReceivedMessages(ctx, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.GetReceivedMessagesResponse{
		Messages: utils.MapSlice(messages, func(message *entities.Message) *generated.Message {
			return &generated.Message{
				Id:           message.ID,
				Content:      message.Content,
				FromNickname: message.FromNickname,
				ToNickname:   message.ToNickname,
				CreatedAt:    message.CreatedAt.Format(time.RFC3339),
			}
		}),
	}, nil
}

func (s *Server) GetSentMessages(ctx context.Context, req *generated.GetSentMessagesRequest) (*generated.GetSentMessagesResponse, error) {
	messages, err := s.messagesService.GetSentMessages(ctx, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.GetSentMessagesResponse{
		Messages: utils.MapSlice(messages, func(message *entities.Message) *generated.Message {
			return &generated.Message{
				Id:           message.ID,
				Content:      message.Content,
				FromNickname: message.FromNickname,
				ToNickname:   message.ToNickname,
				CreatedAt:    message.CreatedAt.Format(time.RFC3339),
			}
		}),
	}, nil
}
