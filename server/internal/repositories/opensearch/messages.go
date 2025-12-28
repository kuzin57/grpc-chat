package chat

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sort"
	"time"

	"github.com/google/uuid"
	"github.com/kuzin57/grpc-chat/server/internal/entities"
	"github.com/kuzin57/grpc-chat/server/internal/utils"
)

const (
	defaultSearchSize  = 100
	lastMessagesAmount = 100
)

func (r *Repository) CreateMessage(ctx context.Context, message entities.Message) (string, error) {
	if message.ID == "" {
		message.ID = uuid.NewString()
	}

	if err := indexDocument(ctx, r.opensearchClient, indexMessages, message.ID, message); err != nil {
		return "", err
	}

	return message.ID, nil
}

func (r *Repository) GetMessages(ctx context.Context, chatID string) ([]*entities.Message, error) {
	query := map[string]any{
		"query": map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		},
		"sort": []map[string]any{
			{"created_at": map[string]any{"order": "desc"}},
		},
		"size": lastMessagesAmount,
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetMessages query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexMessages),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
		r.opensearchClient.Search.WithSize(lastMessagesAmount),
	)
	if err != nil {
		return nil, fmt.Errorf("search messages: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []*entities.Message{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search messages error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Hits []struct {
				Source entities.Message `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode messages response: %w", err)
	}

	result := make([]*entities.Message, 0, len(parsed.Hits.Hits))
	for _, h := range parsed.Hits.Hits {
		m := h.Source
		result = append(result, &m)
	}

	sort.Slice(result, func(i, j int) bool {
		return result[i].CreatedAt.Before(result[j].CreatedAt)
	})

	return result, nil
}

func (r *Repository) SearchMessages(ctx context.Context, chatID, query string, tags []string, offset int) ([]*entities.Message, string, error) {
	boolQuery := map[string]any{}

	filters := []map[string]any{
		{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		},
	}

	switch {
	case len(query) <= 2 && len(query) > 0:
		boolQuery["must"] = []map[string]any{
			{
				"prefix": map[string]any{
					"content": map[string]any{
						"value":            query,
						"case_insensitive": true,
					},
				},
			},
		}
	case len(query) > 0:
		boolQuery["must"] = []map[string]any{
			{
				"match": map[string]any{
					"content": map[string]any{
						"query":                query,
						"operator":             "or",
						"fuzziness":            "AUTO",
						"minimum_should_match": "75%",
						"boost":                1.0,
					},
				},
			},
		}
	}

	if len(tags) > 0 {
		filters = append(filters, map[string]any{
			"terms": map[string]any{
				"tags.keyword": tags,
			},
		})
	}

	if len(filters) > 0 {
		boolQuery["filter"] = filters
	}

	var finalQuery map[string]any
	if len(boolQuery) > 0 {
		finalQuery = map[string]any{
			"bool": boolQuery,
		}
	} else {
		finalQuery = map[string]any{
			"match_all": map[string]any{},
		}
	}

	sortField := []map[string]any{
		{"created_at": map[string]any{"order": "desc"}},
	}

	opensearchQuery := map[string]any{
		"query": finalQuery,
		"sort":  sortField,
	}

	data, err := json.Marshal(opensearchQuery)
	if err != nil {
		return nil, "", fmt.Errorf("marshal SearchMessages query: %w", err)
	}

	log.Println("request to OpenSearch:", string(data))

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexMessages),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
		r.opensearchClient.Search.WithScroll(time.Minute*10),
		r.opensearchClient.Search.WithSize(defaultSearchSize),
	)
	if err != nil {
		return nil, "", fmt.Errorf("search messages: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []*entities.Message{}, "", nil
	}

	if res.IsError() {
		return nil, "", fmt.Errorf("search messages error: %s", res.String())
	}

	log.Println("[opensearch] SearchMessages response:", res.String())

	var parsed struct {
		ScrollID string `json:"_scroll_id"`
		Hits     struct {
			Hits []struct {
				Source entities.Message `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, "", fmt.Errorf("decode messages response: %w", err)
	}

	var resultMessages []*entities.Message

	if len(parsed.Hits.Hits) < offset {
		currentOffset := len(parsed.Hits.Hits)
		for currentOffset < offset {
			messages, scrollID, err := r.ScrollMessages(ctx, parsed.ScrollID)
			if err != nil {
				return nil, "", fmt.Errorf("scroll messages: %w", err)
			}

			parsed.ScrollID = scrollID
			if currentOffset+len(messages) > offset {
				resultMessages = append(resultMessages, messages[offset-currentOffset:]...)
			}

			currentOffset += len(messages)
		}
	} else {
		resultMessages = utils.MapSlice(parsed.Hits.Hits[offset:], func(h struct {
			Source entities.Message `json:"_source"`
		}) *entities.Message {
			return &h.Source
		})
	}

	return resultMessages, parsed.ScrollID, nil
}

func (r *Repository) ScrollMessages(ctx context.Context, scrollID string) ([]*entities.Message, string, error) {
	scrollBody := map[string]any{
		"scroll":    "1m",
		"scroll_id": scrollID,
	}

	data, err := json.Marshal(scrollBody)
	if err != nil {
		return nil, "", fmt.Errorf("marshal ScrollMessages query: %w", err)
	}

	res, err := r.opensearchClient.Scroll(
		r.opensearchClient.Scroll.WithContext(ctx),
		r.opensearchClient.Scroll.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, "", fmt.Errorf("scroll messages: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []*entities.Message{}, "", nil
	}

	if res.IsError() {
		return nil, "", fmt.Errorf("scroll messages error: %s", res.String())
	}

	var parsed struct {
		ScrollID string `json:"_scroll_id"`
		Hits     struct {
			Hits []struct {
				Source entities.Message `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, "", fmt.Errorf("decode messages response: %w", err)
	}

	result := make([]*entities.Message, 0, len(parsed.Hits.Hits))
	for _, h := range parsed.Hits.Hits {
		m := h.Source
		result = append(result, &m)
	}

	return result, parsed.ScrollID, nil
}

func (r *Repository) SetMessagesRead(ctx context.Context, chatID, nickname string) error {
	log.Println("[opensearch] SetMessagesRead is not implemented, chatID:", chatID, "nickname:", nickname)
	return nil
}

func (r *Repository) GetTopWords(ctx context.Context, chatID string, limit int) ([]entities.WordStat, error) {
	if limit <= 0 {
		limit = 10
	}

	query := map[string]any{
		"query": map[string]any{
			"match_all": map[string]any{},
		},
		"size": 0,
		"aggs": map[string]any{
			"top_words": map[string]any{
				"terms": map[string]any{
					"field": "content",
					"size":  limit,
				},
			},
		},
	}

	if chatID != "" {
		query["query"] = map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		}
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetTopWords query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexMessages),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, fmt.Errorf("search top words: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []entities.WordStat{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search top words error: %s", res.String())
	}

	var parsed struct {
		Aggregations struct {
			TopWords struct {
				Buckets []struct {
					Key   string `json:"key"`
					Count int64  `json:"doc_count"`
				} `json:"buckets"`
			} `json:"top_words"`
		} `json:"aggregations"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode top words response: %w", err)
	}

	result := make([]entities.WordStat, 0, len(parsed.Aggregations.TopWords.Buckets))
	for _, bucket := range parsed.Aggregations.TopWords.Buckets {
		result = append(result, entities.WordStat{
			Word:  bucket.Key,
			Count: bucket.Count,
		})
	}

	return result, nil
}

func (r *Repository) GetTopTags(ctx context.Context, chatID string, limit int) ([]entities.TagStat, error) {
	if limit <= 0 {
		limit = 10
	}

	query := map[string]any{
		"query": map[string]any{
			"match_all": map[string]any{},
		},
		"size": 0,
		"aggs": map[string]any{
			"top_tags": map[string]any{
				"terms": map[string]any{
					"field": "tags.keyword",
					"size":  limit,
				},
			},
		},
	}

	if chatID != "" {
		query["query"] = map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		}
	}

	data, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("marshal GetTopTags query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexMessages),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return nil, fmt.Errorf("search top tags: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return []entities.TagStat{}, nil
	}

	if res.IsError() {
		return nil, fmt.Errorf("search top tags error: %s", res.String())
	}

	var parsed struct {
		Aggregations struct {
			TopTags struct {
				Buckets []struct {
					Key   string `json:"key"`
					Count int64  `json:"doc_count"`
				} `json:"buckets"`
			} `json:"top_tags"`
		} `json:"aggregations"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode top tags response: %w", err)
	}

	result := utils.MapSlice(parsed.Aggregations.TopTags.Buckets, func(bucket struct {
		Key   string `json:"key"`
		Count int64  `json:"doc_count"`
	}) entities.TagStat {
		return entities.TagStat{
			Tag:   bucket.Key,
			Count: bucket.Count,
		}
	})

	return result, nil
}

func (r *Repository) GetMessagesCount(ctx context.Context, chatID string) (int64, error) {
	query := map[string]any{
		"query": map[string]any{
			"term": map[string]any{
				"chat_id.keyword": chatID,
			},
		},
	}

	data, err := json.Marshal(query)
	if err != nil {
		return 0, fmt.Errorf("marshal GetMessagesCount query: %w", err)
	}

	res, err := r.opensearchClient.Search(
		r.opensearchClient.Search.WithContext(ctx),
		r.opensearchClient.Search.WithIndex(indexMessages),
		r.opensearchClient.Search.WithBody(bytes.NewReader(data)),
	)
	if err != nil {
		return 0, fmt.Errorf("search messages count: %w", err)
	}
	defer res.Body.Close()

	if res.StatusCode == 404 {
		return 0, nil
	}

	if res.IsError() {
		return 0, fmt.Errorf("search messages count error: %s", res.String())
	}

	var parsed struct {
		Hits struct {
			Total struct {
				Value int64 `json:"value"`
			} `json:"total"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&parsed); err != nil {
		return 0, fmt.Errorf("decode messages count response: %w", err)
	}

	return parsed.Hits.Total.Value, nil
}
