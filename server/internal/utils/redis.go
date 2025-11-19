package utils

import (
	"fmt"
	"strings"
)

const (
	chatIDKeyPosition       = 1
	userNicknameKeyPosition = 2
)

func BuildChatUserKey(chatID, nickname string) string {
	return fmt.Sprintf("chat_user:%s:%s", chatID, nickname)
}

func BuildChatUserPatternByChat(chatID string) string {
	return fmt.Sprintf("chat_user:%s:*", chatID)
}

func BuildChatUserPatternByUser(nickname string) string {
	return fmt.Sprintf("chat_user:*:%s", nickname)
}

func ExtractChatIDFromChatUserKey(key string) string {
	return strings.Split(key, ":")[chatIDKeyPosition]
}

func ExtractNicknameFromChatUserKey(key string) string {
	return strings.Split(key, ":")[userNicknameKeyPosition]
}

func BuildChatMessageKey(chatID, messageID string) string {
	return fmt.Sprintf("chat_message:%s:%s", chatID, messageID)
}

func BuildChatMessagePatternByChat(chatID string) string {
	return fmt.Sprintf("chat_message:%s:*", chatID)
}
