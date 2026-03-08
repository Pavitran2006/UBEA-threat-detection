# UEBA Multi-Tenant SaaS Architecture (EKS)

```text
                           +---------------------------+
                           | Route53 + CloudFront + WAF|
                           +------------+--------------+
                                        |
                               +--------v--------+
                               | API Gateway/ALB |
                               +--------+--------+
                                        |
         +------------------------------+------------------------------+
         |                EKS (Tenant-Aware Namespace)               |
         |                                                            |
         |  +------------------+   +------------------+              |
         |  | auth-service     |-->| risk-service      |<---+        |
         |  +--------+---------+   +--------+----------+    |        |
         |           |                      |               |        |
         |           |   +------------------v----------+    |        |
         |           +-->| Kafka (login/anomaly/risk) |----+        |
         |               +------------------+----------+             |
         |                                  |                        |
         |                    +-------------v--------------+         |
         |                    | analytics-ml-service       |         |
         |                    | IsolationForest + MLflow   |         |
         |                    +-------------+--------------+         |
         |                                  |                        |
         |                       +----------v---------+              |
         |                       | session-monitoring |              |
         |                       +----------+---------+              |
         |                                  |                        |
         +----------------------------------+------------------------+
                                            |
                 +--------------------------+------------------------+
                 |                                                   |
      +----------v---------+                           +-------------v------------+
      | Aurora/RDS (tenant)|                           | Elasticsearch (tenant idx)|
      +--------------------+                           +--------------------------+
                 |
      +----------v----------+
      | MLflow Registry     |
      | Drift + Canary Roll |
      +---------------------+
```

## Tenant Isolation Controls
- `tenant_id` required in JWT claims and Kafka payloads
- DB access filtered by `tenant_id` at service boundary
- Elasticsearch index pattern `tenant-{tenant_id}-*`
- Per-tenant model names in MLflow (`login-iforest-{tenant_id}`)
- NetworkPolicy namespace segmentation + mTLS

