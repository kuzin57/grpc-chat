package entities

import "time"

type Message struct {
	ID        string    `json:"id" redis:"id"`
	Content   string    `json:"content" redis:"content"`
	Nickname  string    `json:"nickname" redis:"nickname"`
	ChatID    string    `json:"chat_id" redis:"chat_id"`
	CreatedAt time.Time `json:"created_at" redis:"created_at"`
}
