# Global Multi-Region AI Threat Intelligence Platform

```text
                        +-----------------------------------+
                        | Route53 Latency + Health Checks   |
                        +-----------+-----------+-----------+
                                    |           |
        +---------------------------+-----------+---------------------------+
        |                           |           |                           |
+-------v--------+         +--------v-------+  +v--------------+  +---------v-------+
| us-east-1      |         | eu-west-1      |  | ap-south-1    |  | Central Control |
| EKS + Kafka    |         | EKS + Kafka    |  | EKS + Kafka   |  | Plane           |
| Aurora Regional|         | Aurora Regional|  | Aurora Reg.   |  | (global model)  |
| Elasticsearch  |         | Elasticsearch  |  | Elasticsearch |  +-----------------+
+-------+--------+         +--------+-------+  +------+--------+
        |                           |                 |
        +----------- MirrorMaker2 --+-----------------+
                        (topic replication)

              +--------------------------------------------------+
              | Aurora Global Database (writer + read replicas) |
              +--------------------------------------------------+

              +--------------------------------------------------+
              | Elasticsearch CCR (cross-cluster replication)    |
              +--------------------------------------------------+
```

## Region Interaction
```text
Tenant traffic -> nearest region via latency routing
Regional auth/risk/analytics decisions -> local Kafka
Regional anomaly summaries -> global topic via MM2
Global meta-model trainer -> publishes signed model bundles
Regional model fetcher -> canary rollout -> full rollout
```

## DR Targets
- RTO: < 5 minutes
- RPO: < 1 minute
- Automated failover: Route53 + cluster health + Aurora global failover
- Backups: PITR for Aurora, snapshot lifecycle for Elasticsearch, object-locked model artifacts

