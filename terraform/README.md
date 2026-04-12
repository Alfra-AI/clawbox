# ClawBox Cloud Deployment

Terraform configuration for deploying ClawBox to AWS.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                            AWS                                   │
│  ┌─────────────┐                                                │
│  │     ALB     │◄──── Internet                                  │
│  └──────┬──────┘                                                │
│         │                                                        │
│  ┌──────▼──────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   ECS       │────►│     RDS     │     │     S3      │       │
│  │  (Fargate)  │     │ (PostgreSQL │     │   (Files)   │       │
│  │             │────►│ + pgvector) │     │             │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Resources Created

- **VPC** with public and private subnets
- **S3 Bucket** for file storage (encrypted, versioned)
- **RDS PostgreSQL** instance with pgvector support
- **ECR Repository** for Docker images
- **ECS Cluster** (Fargate) for running the application
- **Application Load Balancer** for traffic routing
- **CloudWatch Log Group** for container logs
- **IAM Roles** for ECS task execution and S3 access

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [Docker](https://www.docker.com/) for building images

## Deployment Steps

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

Required variables:
- `db_password` - Secure password for RDS
- `openai_api_key` - OpenAI API key (for semantic search)

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

### 4. Deploy Infrastructure

```bash
terraform apply
```

Note the outputs:
- `api_url` - Your API endpoint
- `ecr_repository_url` - Where to push Docker images

### 5. Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t clawbox .

# Tag and push
docker tag clawbox:latest <ecr_repository_url>:latest
docker push <ecr_repository_url>:latest
```

### 6. Initialize pgvector Extension

Connect to RDS and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 7. Force ECS Service Update

```bash
aws ecs update-service --cluster clawbox-prod-cluster --service clawbox-prod --force-new-deployment
```

## Accessing the API

The API will be available at the ALB DNS name:
```bash
curl http://<alb-dns-name>/health
```

## CLI Configuration

Configure the CLI to use the cloud API:
```bash
clawbox config --api-url http://<alb-dns-name>
clawbox init
```

## Costs

Estimated monthly costs (us-east-1, minimal config):
- ECS Fargate (256 CPU, 512 MB): ~$10
- RDS db.t3.micro: ~$15
- ALB: ~$16
- S3: ~$1 (depends on storage)
- **Total**: ~$40-50/month

## Cleanup

```bash
terraform destroy
```

## Production Considerations

For production, consider:
1. **HTTPS** - Add ACM certificate and HTTPS listener
2. **Domain** - Configure Route53 with custom domain
3. **Larger instances** - Scale RDS and ECS as needed
4. **Multi-AZ RDS** - Enable for high availability
5. **Auto-scaling** - Add ECS auto-scaling policies
6. **Secrets Manager** - Store sensitive values securely
7. **WAF** - Add Web Application Firewall
8. **Backups** - Configure RDS automated backups
