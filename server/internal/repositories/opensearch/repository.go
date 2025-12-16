package chat

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"

	"github.com/kuzin57/grpc-chat/server/internal/config"
	"github.com/opensearch-project/opensearch-go/v2"
	"github.com/opensearch-project/opensearch-go/v2/opensearchapi"
)

const (
	indexChats     = "chats"
	indexChatUsers = "chat_users"
	indexMessages  = "messages"
)

type Repository struct {
	opensearchClient *opensearch.Client
}

func NewRepository(config *config.Config) (*Repository, error) {
	opensearchClient, err := initOpensearchClient(config)
	if err != nil {
		return nil, err
	}

	return &Repository{opensearchClient: opensearchClient}, nil
}

func initOpensearchClient(config *config.Config) (*opensearch.Client, error) {
	opensearchClient, err := opensearch.NewClient(opensearch.Config{
		Addresses: []string{"http://" + config.Opensearch.Host + ":" + config.Opensearch.Port},
		Username:  config.Opensearch.User,
		Password:  config.Opensearch.Password,
	})
	if err != nil {
		return nil, err
	}

	_, err = opensearchClient.Ping()
	if err != nil {
		return nil, err
	}

	return opensearchClient, nil
}

func indexDocument(ctx context.Context, client *opensearch.Client, index, id string, body any) error {
	data, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal body for index %s: %w", index, err)
	}

	req := opensearchapi.IndexRequest{
		Index:      index,
		DocumentID: id,
		Body:       bytes.NewReader(data),
		Refresh:    "true",
	}

	res, err := req.Do(ctx, client)
	if err != nil {
		return fmt.Errorf("index request to %s failed: %w", index, err)
	}
	defer res.Body.Close()

	if res.IsError() {
		return fmt.Errorf("index %s id %s error: %s", index, id, res.String())
	}

	return nil
}
