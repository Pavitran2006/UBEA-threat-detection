# SaaS Deployment Instructions

## Prerequisites
- AWS CLI configured
- `kubectl` and `helm` installed
- `terraform` for EKS provisioning

## 1. AWS Infrastructure (EKS)
Provision the cluster using AWS CDK or Terraform.
```bash
aws eks update-kubeconfig --name ueba-saas-cluster --region us-east-1
```

## 2. Shared Services (Kafka & Redis)
Deploy Kafka using the Strimzi operator or Amazon MSK.
```bash
helm repo add strimzi https://strimzi.io/charts/
helm install ueba-kafka strimzi/strimzi-kafka-operator
```

## 3. Database Isolation Strategy
We use **Discriminator Column** partitioning for the data layer.
- RDS MySQL instance: `mysql-service.ueba-system.svc.cluster.local`
- Connectivity handled via `sqlalchemy` with `tenant_id` filters in the ORM layer.

## 4. Application Deployment
Apply the unified manifests:
```bash
kubectl apply -f k8s/common.yaml
kubectl apply -f k8s/gateway.yaml
kubectl apply -f k8s/analytics.yaml
kubectl apply -f k8s/risk.yaml
```

## 5. Observability Stack
Access the dashboards:
- **Grafana**: `http://grafana.ueba-saas.com`
- **MLflow**: `http://mlflow.ueba-saas.com`
- **Dashboards**: [Grafana JSON Exporter](k8s/dashboards/ueba-main.json)

## 6. CI/CD Pipeline
Merging to `main` triggers:
1. Docker Build & Push to Amazon ECR.
2. `kubectl rollout restart deployment/gateway-service`.
3. Canary validation for ML models.
