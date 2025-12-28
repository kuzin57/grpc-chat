curl -X PUT http://localhost:9200/messages/_mapping -H 'Content-Type: application/json' -d '{"properties":{"content":{"type":"text","fielddata":true}}}'
