variable "project_id" {
  type        = string
  description = "GCP Project ID for Agent Operations Analytics Pipeline deployment"
  default     = "agent-ops-analytics-prod"
}

variable "region" {
  type        = string
  description = "GCP Region for Cloud Run and BigQuery"
  default     = "us-central1"
}

variable "dataset_raw_name" {
  type        = string
  description = "BigQuery dataset name for raw telemetry events and runs"
  default     = "agent_ops_raw"
}

variable "dataset_views_name" {
  type        = string
  description = "BigQuery dataset name for versioned analytical views and grades"
  default     = "agent_ops_analytics"
}

variable "container_image" {
  type        = string
  description = "Container image URI for pipeline jobs on Cloud Run"
  default     = "gcr.io/agent-ops-analytics-prod/agent-ops-engine:v0.1.0"
}
