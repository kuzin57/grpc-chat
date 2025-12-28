package chat

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
	"github.com/opensearch-project/opensearch-go/v2/opensearchapi"
)

func (r *Repository) AddUserToChat(ctx context.Context, chatID, nickname string) error {
	docID := utils.BuildChatUserKey(chatID, nickname)

	userDoc := entities.ChatUser{
		ChatID:      chatID,
		Nickname:    nickname,
		NewMessages: 0,
	}

	if err := indexDocument(ctx, r.opensearchClient, indexChatUsers, docID, userDoc); err != nil {
		return err
	}

	log.Println("[opensearch] Added user to chat", chatID, "nickname", nickname)
	return nil
}

func (r *Repository) RemoveUserFromChat(ctx context.Context, chatID, nickname string) error {
	docID := utils.BuildChatUserKey(chatID, nickname)

	req := opensearchapi.DeleteRequest{
		Index:      indexChatUsers,
		DocumentID: docID,
		Refresh:    "true",
	}

	res, err := req.Do(ctx, r.opensearchClient)
	if err != nil {
		return fmt.Errorf("delete chat_user %s from opensearch: %w", docID, err)
	}
	defer res.Body.Close()

	if res.IsError() && res.StatusCode != 404 {
		return fmt.Errorf("delete chat_user %s error: %s", docID, res.String())
	}

	return nil
}

func (r *Repository) GetUserChats(ctx context.Context, nickname string) ([]string, error) {
	query := map[string]any{
		"query": map[string]any{
			"term": map[string]any{
				"nickname.keyword": nickname,
			},
		},
		"_source": []string{"chat_id"},
		"size":    1000,
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetUserChats query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexChatUsers),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, fmt.Errorf("search user chats: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []string{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search user chats error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Hits []struct {
				Source struct {
					ChatID string `json:"chat_id"`
				} `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode user chats response: %w", err)
	}

	result := make([]string, 0, len(parsed.Hits.Hits))
	for _, h := range parsed.Hits.Hits {
		if h.Source.ChatID != "" {
			result = append(result, h.Source.ChatID)
		}
	}

	return result, nil
}

func (r *Repository) GetUsersByChatID(ctx context.Context, chatID string) ([]*entities.ChatUser, error) {
	query := map[string]any{
		"query": map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		},
		"size": 1000,
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetUsersByChatID query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexChatUsers),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, fmt.Errorf("search users by chat id: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []*entities.ChatUser{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search users by chat id error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Hits []struct {
				Source entities.ChatUser `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode users by chat id response: %w", err)
	}

	result := make([]*entities.ChatUser, 0, len(parsed.Hits.Hits))
	for _, h := range parsed.Hits.Hits {
		u := h.Source
		result = append(result, &u)
	}

	return result, nil
}

func (r *Repository) GetUsersCount(ctx context.Context, chatID string) (int64, error) {
	query := map[string]any{
		"query": map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		},
	}

	data, err := json.Marshal(query)
	if err != nil {
		return 0, fmt.Errorf("marshal GetUsersCount query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexChatUsers),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return 0, fmt.Errorf("search users count: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return 0, nil
	}

	if res.IsError() {
		return 0, fmt.Errorf("search users count error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Total struct {
				Value int64 `json:"value"`
			} `json:"total"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return 0, fmt.Errorf("decode users count response: %w", err)
	}

	return parsed.Hits.Total.Value, nil
}
