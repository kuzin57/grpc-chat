# Simple grpc chat server written in Go and AI-generated console client written in Python.

## How to run?

### Run server
```
docker-compose up -d --build
```

### Simple chat (without streaming)
```
python3 simple_console_chat.py localhost:8080
```

### Console chat (with streaming) with messages storage in Redis
```
python3 redis_based_console_chat.py --server localhost:8080
```

Video recording link - https://drive.google.com/file/d/1HOymkSwxoqhAtQdrxmxwN4I56XhHAP2Y/view?usp=sharing 

### Console chat (with streaming) with messages storage in Opensearch
After running the server, you need to create an index in Opensearch:
```
curl -X PUT "http://localhost:9200/messages"
```

And set fielddata to true for the content field:
```
./scripts/add_fielddata_to_content_field.sh
```

To fill database with test messages you can use
```
python3 fill_chat.py <chat_id> <nickname> --count <count>
```

```
python3 console_chat.py --server localhost:8080
```
