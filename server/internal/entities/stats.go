package entities

type WordStat struct {
	Word  string
	Count int64
}

type TagStat struct {
	Tag   string
	Count int64
}

type ChatStats struct {
	UsersCount    int64
	MessagesCount int64
	Words         []WordStat
	Tags          []TagStat
}
