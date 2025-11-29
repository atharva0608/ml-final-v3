# CloudOptim Infrastructure

Infrastructure as Code for CloudOptim agentless Kubernetes cost optimization platform.

## 📋 Contents

- `docker-compose.yml` - Local development environment
- `kubernetes/` - Kubernetes manifests for production
- `terraform/` - Terraform modules for AWS infrastructure

---

## 🚀 Local Development with Docker Compose

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### Quick Start

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Check service status**:
   ```bash
   docker-compose ps
   ```

3. **View logs**:
   ```bash
   # All services
   docker-compose logs -f

   # Specific service
   docker-compose logs -f ml-server
   docker-compose logs -f core-platform
   ```

4. **Stop all services**:
   ```bash
   docker-compose down
   ```

5. **Stop and remove volumes** (clean slate):
   ```bash
   docker-compose down -v
   ```

### Service URLs

- **Core Platform API**: http://localhost:8000
- **ML Server API**: http://localhost:8001
- **Admin Frontend**: http://localhost:3000
- **ML Frontend**: http://localhost:3001
- **PostgreSQL (Core)**: localhost:5432
- **PostgreSQL (ML)**: localhost:5433
- **Redis**: localhost:6379

### Health Checks

```bash
# Core Platform
curl http://localhost:8000/health

# ML Server
curl http://localhost:8001/health
```

---

## ☸️ Kubernetes Deployment

### Prerequisites
- Kubernetes cluster (EKS, GKE, AKS, or local)
- `kubectl` configured
- Helm 3+ (optional)

### Setup

1. **Create namespace**:
   ```bash
   kubectl create namespace cloudoptim
   ```

2. **Create secrets**:
   ```bash
   # ML Server secrets
   kubectl create secret generic ml-server-secrets \
     --from-literal=database-url="postgresql://user:pass@host:5432/ml_server_db" \
     --from-literal=redis-url="redis://redis:6379/0" \
     --from-literal=jwt-secret-key="your-jwt-secret" \
     --from-literal=api-key-salt="your-api-key-salt" \
     -n cloudoptim

   # Core Platform secrets
   kubectl create secret generic core-platform-secrets \
     --from-literal=database-url="postgresql://user:pass@host:5432/core_platform_db" \
     --from-literal=redis-url="redis://redis:6379/1" \
     --from-literal=jwt-secret-key="your-jwt-secret" \
     --from-literal=api-key-salt="your-api-key-salt" \
     -n cloudoptim
   ```

3. **Deploy ML Server**:
   ```bash
   kubectl apply -f kubernetes/ml-server/deployment.yaml
   ```

4. **Deploy Core Platform**:
   ```bash
   kubectl apply -f kubernetes/core-platform/deployment.yaml
   ```

5. **Verify deployments**:
   ```bash
   kubectl get pods -n cloudoptim
   kubectl get services -n cloudoptim
   ```

### Scaling

```bash
# Scale ML Server
kubectl scale deployment ml-server --replicas=4 -n cloudoptim

# Scale Core Platform
kubectl scale deployment core-platform --replicas=4 -n cloudoptim
```

---

## 🌐 Terraform (AWS Infrastructure)

### Prerequisites
- Terraform 1.0+
- AWS CLI configured
- AWS account with appropriate permissions

### Setup

1. **Initialize Terraform**:
   ```bash
   cd terraform/
   terraform init
   ```

2. **Plan infrastructure**:
   ```bash
   terraform plan -out=tfplan
   ```

3. **Apply infrastructure**:
   ```bash
   terraform apply tfplan
   ```

### What Terraform Creates

- **VPC**: Virtual Private Cloud with public/private subnets
- **EKS Cluster**: Kubernetes cluster for CloudOptim
- **RDS PostgreSQL**: Managed databases (Core Platform + ML Server)
- **ElastiCache Redis**: Managed Redis cluster
- **EventBridge Rules**: Spot interruption event routing
- **SQS Queues**: Event queues for Core Platform
- **IAM Roles**: Service accounts with least-privilege permissions
- **S3 Buckets**: Model storage and backups

### Terraform Outputs

```bash
# Get outputs
terraform output

# Specific output
terraform output eks_cluster_endpoint
terraform output rds_core_endpoint
terraform output rds_ml_endpoint
```

---

## 🔐 Security

### Secrets Management

**Development**: Use `docker-compose.yml` environment variables

**Production**: Use Kubernetes secrets + AWS Secrets Manager

```bash
# Create secret from AWS Secrets Manager
kubectl create secret generic ml-server-secrets \
  --from-literal=database-url="$(aws secretsmanager get-secret-value --secret-id ml-server-db-url --query SecretString --output text)" \
  -n cloudoptim
```

### Network Security

- All services communicate via private network
- External access only through Load Balancer/Ingress
- Database access restricted to application pods
- Redis access restricted to application pods

---

## 📊 Monitoring

### Logs

```bash
# Docker Compose
docker-compose logs -f ml-server

# Kubernetes
kubectl logs -f deployment/ml-server -n cloudoptim
```

### Metrics

**Kubernetes**:
```bash
kubectl top pods -n cloudoptim
kubectl top nodes
```

**Prometheus/Grafana** (if installed):
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

---

## 🛠️ Troubleshooting

### Service Won't Start

1. **Check dependencies**:
   ```bash
   docker-compose ps
   ```

2. **Check logs**:
   ```bash
   docker-compose logs ml-server
   ```

3. **Restart service**:
   ```bash
   docker-compose restart ml-server
   ```

### Database Connection Issues

1. **Verify database is running**:
   ```bash
   docker-compose ps postgres-ml
   ```

2. **Test connection**:
   ```bash
   docker-compose exec postgres-ml psql -U ml_server -d ml_server_db
   ```

### Kubernetes Pod Crashes

1. **Check pod status**:
   ```bash
   kubectl describe pod <pod-name> -n cloudoptim
   ```

2. **Check logs**:
   ```bash
   kubectl logs <pod-name> -n cloudoptim --previous
   ```

3. **Check secrets**:
   ```bash
   kubectl get secrets -n cloudoptim
   ```

---

## 🔄 Updates and Maintenance

### Update Docker Images

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d
```

### Update Kubernetes Deployments

```bash
# Update image
kubectl set image deployment/ml-server ml-server=cloudoptim/ml-server:v2.0.0 -n cloudoptim

# Rollback if needed
kubectl rollout undo deployment/ml-server -n cloudoptim

# Check rollout status
kubectl rollout status deployment/ml-server -n cloudoptim
```

---

## 📚 Additional Resources

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Kubernetes Docs](https://kubernetes.io/docs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

**Last Updated**: 2025-11-29
