package server

import (
	"context"
	"errors"
	"io"
	"log"
	"sync"
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

	streams map[string]generated.Messenger_ChatStreamServer
	mu      *sync.RWMutex
}

func NewServer(messengerService MessengerService) *Server {
	return &Server{
		messengerService: messengerService,
		mu:               &sync.RWMutex{},
		streams:          make(map[string]generated.Messenger_ChatStreamServer),
	}
}

func (s *Server) SendMessage(ctx context.Context, req *generated.SendMessageRequest) (*generated.SendMessageResponse, error) {
	log.Println("Sending message:", req.Message, "chat", req.ChatId)

	message, err := s.messengerService.SendMessage(ctx, req.Message, req.Nickname, req.ChatId)
	if err != nil {
		if errors.Is(err, repository.ErrChatNotFound) {
			return nil, status.Errorf(codes.NotFound, "chat not found")
		}

		return nil, err
	}

	return &generated.SendMessageResponse{
		MessageId: message.ID,
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
		Chats: utils.MapSliceIf(chats, func(chatID string) (*generated.ChatStats, bool) {
			chatUser, ok := chatUsers[chatID]
			if !ok {
				return nil, false
			}

			return &generated.ChatStats{
				NewMessages: int32(chatUser.NewMessages),
				ChatId:      chatID,
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

func (s *Server) ChatStream(stream generated.Messenger_ChatStreamServer) error {
	for {
		ctx := stream.Context()

		select {
		case <-ctx.Done():
			log.Println("Stream context cancelled")
			return ctx.Err()
		default:
		}

		req, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			log.Println("Chat stream EOF")
			break
		}

		if err != nil {
			log.Println("Chat stream error:", err)
			return err
		}

		message := entities.Message{
			Content:   req.Content,
			Nickname:  req.Nickname,
			ChatID:    req.ChatId,
			CreatedAt: time.Now(),
		}

		log.Println("[Chat stream] message:", message)
		log.Println("[Chat stream] message type:", req.Type)

		switch req.Type {
		case generated.ChatMessageType_MESSAGE:
			message, err = s.messengerService.SendMessage(ctx, req.Content, req.Nickname, req.ChatId)
			if err != nil {
				log.Println("Chat stream error:", err)
				continue
			}

			s.mu.Lock()
			s.streams[req.Nickname] = stream
			s.mu.Unlock()

			log.Println("Chat stream message:", message)
		case generated.ChatMessageType_USER_CONNECTED:
			s.mu.Lock()
			s.streams[req.Nickname] = stream
			s.mu.Unlock()

			if req.Content == "heartbeat" {
				log.Println("Heartbeat received from:", req.Nickname)
				continue
			}

			log.Println("User connected and registered:", req.Nickname)
			continue
		case generated.ChatMessageType_USER_JOINED:
			if err = s.messengerService.SetMessagesRead(ctx, req.ChatId, req.Nickname); err != nil {
				log.Println("Chat stream error:", err)
				continue
			}

			s.mu.Lock()
			s.streams[req.Nickname] = stream
			s.mu.Unlock()
			log.Printf("User %s joined chat %s, total active streams: %d", req.Nickname, req.ChatId, len(s.streams))

			select {
			case <-ctx.Done():
				log.Printf("Stream context cancelled for user %s, skipping broadcast", req.Nickname)
				continue
			default:
			}
		case generated.ChatMessageType_USER_GOT_IN:
			if err = s.messengerService.SetMessagesRead(ctx, req.ChatId, req.Nickname); err != nil {
				log.Println("Chat stream error:", err)
				continue
			}

			s.mu.Lock()
			s.streams[req.Nickname] = stream
			s.mu.Unlock()

			messages, err := s.messengerService.GetMessages(ctx, req.ChatId)
			if err != nil {
				log.Println("Chat stream error:", err)
				continue
			}

			for _, message := range messages {
				log.Println("Sending message to user", message.Nickname, "message", message)

				if err := stream.Send(&generated.ChatMessage{
					Id:        message.ID,
					Content:   message.Content,
					Nickname:  message.Nickname,
					ChatId:    message.ChatID,
					CreatedAt: message.CreatedAt.Format(time.RFC3339),
					Type:      generated.ChatMessageType_MESSAGE,
				}); err != nil {
					log.Println("Chat stream error:", err)
					continue
				}
			}

			log.Println("Chat stream messages sent:", req.ChatId, "nickname", req.Nickname)
			continue
		case generated.ChatMessageType_USER_LEFT:
			s.mu.Lock()
			delete(s.streams, req.Nickname)
			s.mu.Unlock()

			log.Println("Chat stream user left:", req.ChatId, "nickname", req.Nickname)
		default:
			log.Println("Unknown chat message type:", req.Type)
			continue
		}

		broadcastCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		err = s.messengerService.Broadcast(broadcastCtx, message, req.Type, s.streams, s.mu)
		cancel()
		if err != nil {
			log.Printf("Broadcast error (non-fatal): %v", err)
		}
	}

	return nil
}
