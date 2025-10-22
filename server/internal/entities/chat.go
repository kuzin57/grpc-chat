package entities

import "time"

type Chat struct {
	ID        string    `json:"id"`
	CreatedAt time.Time `json:"created_at"`
}

type ChatUser struct {
	ChatID      string    `json:"chat_id"`
	Nickname    string    `json:"nickname"`
	JoinedAt    time.Time `json:"joined_at"`
	NewMessages int       `json:"new_messages"`
}
