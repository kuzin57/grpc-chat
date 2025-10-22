.PHONY: proto build run clean docker-build docker-run docker-stop docker-clean deps

proto:
	protoc --go_out=. --go-grpc_out=. proto/messenger.proto
	mv github.com/kuzin57/grpc-chat/server/internal/generated/*.pb.go server/internal/generated/
	rm -rf github.com internal

proto-python:
	python3 -m grpc_tools.protoc --proto_path=proto --python_out=./client --grpc_python_out=./client proto/messenger.proto
	mv client/messenger_pb2.py client/generated/
	mv client/messenger_pb2_grpc.py client/generated/
	cd client && ln -sf generated/messenger_pb2.py messenger_pb2.py

clean:
	rm -rf bin/
	rm -f server/internal/generated/*.pb.go
	rm -f client/messenger_pb2.py

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
