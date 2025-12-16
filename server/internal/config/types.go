package config

type Config struct {
	Port          string           `yaml:"port"`
	Redis         RedisConfig      `yaml:"redis"`
	Opensearch    OpensearchConfig `yaml:"opensearch"`
	UseOpensearch bool             `yaml:"use_opensearch"`
}

type RedisConfig struct {
	Host     string `yaml:"host"`
	Port     string `yaml:"port"`
	Password string `yaml:"password"`
	User     string `yaml:"user"`
}

type OpensearchConfig struct {
	Host     string `yaml:"host"`
	Port     string `yaml:"port"`
	Password string `yaml:"password"`
	User     string `yaml:"user"`
}
