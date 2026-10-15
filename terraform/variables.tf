variable "aws_region" {
  description = "AWS Region to deploy Mission Control (Bangkok)"
  type        = string
  default     = "ap-southeast-7"
}

variable "project_name" {
  description = "Project name prefix for tags and resources"
  type        = string
  default     = "mission-control"
}

variable "instance_type" {
  description = "EC2 Instance Type (Free Tier eligible / low-cost)"
  type        = string
  default     = "t3.micro"
}

variable "ebs_volume_size" {
  description = "Root EBS storage size in GB (Free Tier eligible up to 30GB)"
  type        = number
  default     = 20
}
