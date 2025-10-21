.PHONY: proto build run clean docker-build docker-run docker-stop docker-clean deps

# Генерация gRPC кода из proto файлов
proto:
	protoc --go_out=. --go-grpc_out=. proto/messenger.proto
	mv github.com/kuzin57/grpc-chat/server/internal/generated/*.pb.go server/internal/generated/
	rm -rf github.com internal

# Добавить в Makefile команду для Python
proto-python:
	python3 -m grpc_tools.protoc --proto_path=proto --python_out=client/generated --grpc_python_out=client/generated proto/messenger.proto

# Сборка сервера
build:
	cd server && go build -o ../bin/server ./internal/cmd

# Запуск сервера
run:
	cd server && go run ./internal/cmd

# Очистка
clean:
	rm -rf bin/
	rm -f server/internal/generated/*.pb.go

# Установка зависимостей
deps:
	go mod tidy
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Docker команды
docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f grpc-server

docker-clean:
	docker-compose down -v
	docker system prune -f

# Полная очистка
clean-all: clean docker-clean
