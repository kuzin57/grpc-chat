package entities

type ChatUser struct {
	ChatID      string `json:"chat_id" redis:"chat_id"`
	Nickname    string `json:"nickname" redis:"nickname"`
	NewMessages int    `json:"new_messages" redis:"new_messages"`
}
