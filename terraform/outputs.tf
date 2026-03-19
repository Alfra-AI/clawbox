output "api_url" {
  description = "API URL (ALB DNS)"
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}

output "s3_bucket_name" {
  description = "S3 bucket name for file storage"
  value       = aws_s3_bucket.files.id
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
}

output "database_url" {
  description = "Database connection string"
  value       = "postgresql://${var.db_username}:****@${aws_db_instance.main.endpoint}/agentbox"
  sensitive   = true
}
