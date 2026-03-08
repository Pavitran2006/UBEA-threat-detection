```text
1. Region model service computes tenant-local gradients/embeddings
2. PII stripped + DP noise added
3. Publish to kafka topic: global.federated_updates
4. Global aggregator trains meta-model
5. Register model in MLflow: global-ueba-meta-model
6. Canary distribute to 10% traffic in each region
7. Promotion gate on:
   - false positive delta
   - precision@k
   - drift score
8. Full rollout to all regional model gateways
```

