package config

type Config struct {
	Port  string      `yaml:"port"`
	Redis RedisConfig `yaml:"redis"`
}

type RedisConfig struct {
	Host     string `yaml:"host"`
	Port     string `yaml:"port"`
	Password string `yaml:"password"`
	User     string `yaml:"user"`
}
