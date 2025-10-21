package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/kuzin57/grpc-chat/server/internal/generated"
	messageRepo "github.com/kuzin57/grpc-chat/server/internal/repositories/messages"
	"github.com/kuzin57/grpc-chat/server/internal/server"
	"github.com/kuzin57/grpc-chat/server/internal/services/messages"
	"google.golang.org/grpc"
	"gopkg.in/yaml.v2"
)

type GRPCServer struct {
	server *grpc.Server
	port   string
}

func NewGRPCServer(port string) *GRPCServer {
	var (
		grpcServer      = grpc.NewServer()
		messageRepo     = messageRepo.NewRepository()
		messagesService = messages.NewService(messageRepo)
		server          = server.NewServer(messagesService)
	)

	generated.RegisterMessengerServer(grpcServer, server)

	return &GRPCServer{
		server: grpcServer,
		port:   port,
	}
}

func (s *GRPCServer) Start() error {
	listener, err := net.Listen("tcp", "0.0.0.0:"+s.port)
	if err != nil {
		return fmt.Errorf("failed to listen on port %s: %w", s.port, err)
	}

	log.Printf("gRPC server starting on port %s", s.port)

	if err := s.server.Serve(listener); err != nil {
		return fmt.Errorf("failed to serve gRPC server: %w", err)
	}

	return nil
}

func (s *GRPCServer) Stop() {
	log.Println("Stopping gRPC server...")
	s.server.GracefulStop()
}

type Config struct {
	Port string `yaml:"port"`
}

func mustLoadConfig(confPath string) *Config {
	content, err := os.ReadFile(confPath)
	if err != nil {
		panic(err)
	}

	cfg := &Config{}

	if err := yaml.Unmarshal(content, cfg); err != nil {
		panic(err)
	}

	return cfg
}

func main() {
	var confPath string

	flag.StringVar(&confPath, "config", "config.yaml", "path to config file")
	flag.Parse()

	cfg := mustLoadConfig(confPath)

	grpcServer := NewGRPCServer(cfg.Port)

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		if err := grpcServer.Start(); err != nil {
			log.Fatalf("Failed to start gRPC server: %v", err)
		}
	}()

	<-sigChan
	log.Println("Received shutdown signal")

	grpcServer.Stop()
	log.Println("gRPC server stopped")
}
