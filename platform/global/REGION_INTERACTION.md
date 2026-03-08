```text
               +--------------------+
               | Global Threat Hub  |
               | Federated Trainer  |
               +---------+----------+
                         |
             +-----------+-----------+
             |                       |
    +--------v--------+     +--------v--------+
    | us-east-1       |<--->| eu-west-1       |
    | Kafka + MM2     |     | Kafka + MM2     |
    +--------+--------+     +--------+--------+
             |                       |
             +-----------+-----------+
                         |
                 +-------v--------+
                 | ap-south-1     |
                 | Kafka + MM2    |
                 +----------------+

Data exchanged:
- anonymized_anomaly_signatures
- tenant-agnostic_behavior_embeddings
- model_evaluation_metrics
```

