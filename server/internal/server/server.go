package server

import (
	"context"
	"errors"
	"log"
	"time"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/generated"
	"github.com/kuzin57/grpc-chat/server/internal/repository"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	_ generated.MessengerServer = (*Server)(nil)
	_ MessengerServer           = (*Server)(nil)
)

type Server struct {
	generated.UnimplementedMessengerServer
	messengerService MessengerService
}

func NewServer(messengerService MessengerService) *Server {
	return &Server{
		messengerService: messengerService,
	}
}

func (s *Server) SendMessage(ctx context.Context, req *generated.SendMessageRequest) (*generated.SendMessageResponse, error) {
	log.Println("Sending message:", req.Message, "chat", req.ChatId)

	messageID, err := s.messengerService.SendMessage(ctx, req.Message, req.Nickname, req.ChatId)
	if err != nil {
		if errors.Is(err, repository.ErrChatNotFound) {
			return nil, status.Errorf(codes.NotFound, "chat not found")
		}

		return nil, err
	}

	return &generated.SendMessageResponse{
		MessageId: messageID,
	}, nil
}

func (s *Server) GetMessages(ctx context.Context, req *generated.GetMessagesRequest) (*generated.GetMessagesResponse, error) {
	log.Println("Getting received messages for:", req.ChatId)

	messages, err := s.messengerService.GetMessages(ctx, req.ChatId)
	if err != nil {
		if errors.Is(err, repository.ErrChatNotFound) {
			return nil, status.Errorf(codes.NotFound, "chat not found")
		}

		return nil, err
	}

	return &generated.GetMessagesResponse{
		Messages: utils.MapSlice(messages, func(message *entities.Message) *generated.Message {
			return &generated.Message{
				Id:        message.ID,
				Content:   message.Content,
				Nickname:  message.Nickname,
				ChatId:    message.ChatID,
				CreatedAt: message.CreatedAt.Format(time.RFC3339),
			}
		}),
	}, nil
}

func (s *Server) GetUserChats(ctx context.Context, req *generated.GetUserChatsRequest) (*generated.GetUserChatsResponse, error) {
	log.Println("Getting user chats for:", req.Nickname)

	chats, chatUsers, err := s.messengerService.GetUserChats(ctx, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.GetUserChatsResponse{
		Chats: utils.MapSliceIf(chats, func(chat *entities.Chat) (*generated.ChatStats, bool) {
			chatUser, ok := chatUsers[chat.ID]
			if !ok {
				return nil, false
			}

			return &generated.ChatStats{
				NewMessages: int32(chatUser.NewMessages),
				ChatId:      chat.ID,
			}, true
		}),
	}, nil
}

func (s *Server) CreateChat(ctx context.Context, req *generated.CreateChatRequest) (*generated.CreateChatResponse, error) {
	log.Println("Creating chat:", req.Name, "for:", req.Nickname)

	chatID, err := s.messengerService.CreateChat(ctx, req.Name, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.CreateChatResponse{
		ChatId: chatID,
	}, nil
}

func (s *Server) LeaveChat(ctx context.Context, req *generated.LeaveChatRequest) (*generated.LeaveChatResponse, error) {
	log.Println("Leaving chat:", req.ChatId, "for:", req.Nickname)

	err := s.messengerService.RemoveUserFromChat(ctx, req.ChatId, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.LeaveChatResponse{
		Success: true,
	}, nil
}

func (s *Server) JoinChat(ctx context.Context, req *generated.JoinChatRequest) (*generated.JoinChatResponse, error) {
	log.Println("Joining chat:", req.ChatId, "for:", req.Nickname)

	err := s.messengerService.AddUserToChat(ctx, req.ChatId, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.JoinChatResponse{
		Success: true,
	}, nil
}

func (s *Server) SetMessagesRead(ctx context.Context, req *generated.SetMessagesReadRequest) (*generated.SetMessagesReadResponse, error) {
	log.Println("Setting messages read for:", req.ChatId, "for:", req.Nickname)

	err := s.messengerService.SetMessagesRead(ctx, req.ChatId, req.Nickname)
	if err != nil {
		return nil, err
	}

	return &generated.SetMessagesReadResponse{
		Success: true,
	}, nil
}
