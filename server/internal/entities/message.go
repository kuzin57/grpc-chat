package entities

import "time"

type Message struct {
	ID           string    `json:"id"`
	Content      string    `json:"content"`
	ToNickname   string    `json:"nickname"`
	FromNickname string    `json:"from_nickname"`
	CreatedAt    time.Time `json:"created_at"`
}
