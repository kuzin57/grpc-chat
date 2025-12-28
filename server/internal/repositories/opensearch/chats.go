package chat

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/repositories"
	"github.com/opensearch-project/opensearch-go/v2/opensearchapi"
)

func (r *Repository) CreateChat(ctx context.Context, chatID, nickname string) (string, error) {
	chatDoc := map[string]any{
		"id":       chatID,
		"owner":    nickname,
		"chat_id":  chatID,
		"nickname": nickname,
	}

	if err := indexDocument(ctx, r.opensearchClient, indexChats, chatID, chatDoc); err != nil {
		return "", err
	}

	if err := r.AddUserToChat(ctx, chatID, nickname); err != nil {
		return "", err
	}

	return chatID, nil
}

func (r *Repository) GetChat(ctx context.Context, chatID string) (string, error) {
	req := opensearchapi.GetRequest{
		Index:      indexChats,
		DocumentID: chatID,
	}

	res, err := req.Do(ctx, r.opensearchClient)
	if err != nil {
		return "", fmt.Errorf("get chat %s from opensearch: %w", chatID, err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return "", repositories.ErrChatNotFound
	}

	if res.IsError() {
		return "", fmt.Errorf("get chat %s error: %s", chatID, res.String())
	}

	return chatID, nil
}

func (r *Repository) GetChatsUsers(ctx context.Context, nickname string, chatsIDs []string) (map[string]*entities.ChatUser, error) {
	if len(chatsIDs) == 0 {
		return map[string]*entities.ChatUser{}, nil
	}

	terms := make([]map[string]any, 0, len(chatsIDs))
	for _, chatID := range chatsIDs {
		terms = append(terms, map[string]any{
			"term": map[string]any{"chat_id.keyword": chatID},
		})
	}

	query := map[string]any{
		"query": map[string]any{
			"bool": map[string]any{
				"must": []any{
					map[string]any{
						"term": map[string]any{"nickname.keyword": nickname},
					},
					map[string]any{
						"bool": map[string]any{"should": terms},
					},
				},
			},
		},
		"size": 1000,
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetChatsUsers query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexChatUsers),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, fmt.Errorf("search chats users: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return map[string]*entities.ChatUser{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search chats users error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Hits []struct {
				Source entities.ChatUser `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode chats users response: %w", err)
	}

	result := make(map[string]*entities.ChatUser)
	for _, h := range parsed.Hits.Hits {
		chatID := h.Source.ChatID
		if chatID != "" {
			user := h.Source
			u := user
			result[chatID] = &u
		}
	}

	return result, nil
}

func (r *Repository) SetTTLToChat(ctx context.Context, chatID string, ttl int32) error {
	log.Println("[opensearch] SetTTLToChat is not implemented, chatID:", chatID, "ttl:", ttl)
	return nil
}
