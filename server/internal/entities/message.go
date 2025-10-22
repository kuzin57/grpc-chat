package entities

import "time"

type Message struct {
	ID        string    `json:"id"`
	Content   string    `json:"content"`
	Nickname  string    `json:"nickname"`
	ChatID    string    `json:"chat_id"`
	CreatedAt time.Time `json:"created_at"`
}
