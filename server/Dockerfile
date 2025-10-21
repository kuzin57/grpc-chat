FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git protobuf protobuf-dev
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY proto/ ./proto/

COPY server/ ./server/

RUN protoc --go_out=. --go-grpc_out=. proto/messenger.proto
RUN mv github.com/kuzin57/grpc-chat/server/internal/generated/*.pb.go server/internal/generated/ || true
RUN rm -rf github.com internal

RUN cd server && go build -o main ./internal/cmd

CMD ["./server/main", "-config", "./server/config/config.yaml"]
