.PHONY: proto build run clean docker-build docker-run docker-stop docker-clean deps

proto:
	protoc --go_out=. --go-grpc_out=. proto/messenger.proto
	mv github.com/kuzin57/grpc-chat/server/internal/generated/*.pb.go server/internal/generated/
	rm -rf github.com internal

proto-python:
	python3 -m grpc_tools.protoc --proto_path=proto --python_out=client/generated --grpc_python_out=client/generated proto/messenger.proto

clean:
	rm -rf bin/
	rm -f server/internal/generated/*.pb.go

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

clean-all: clean docker-clean
