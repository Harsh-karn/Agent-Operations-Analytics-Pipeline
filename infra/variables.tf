variable "project_id" {
  type        = string
  description = "GCP Project ID for Tally deployment"
  default     = "tally-analytics-prod"
}

variable "region" {
  type        = string
  description = "GCP Region for Cloud Run and BigQuery"
  default     = "us-central1"
}

variable "dataset_raw_name" {
  type        = string
  description = "BigQuery dataset name for raw telemetry events and runs"
  default     = "tally_raw"
}

variable "dataset_views_name" {
  type        = string
  description = "BigQuery dataset name for versioned analytical views and grades"
  default     = "tally_analytics"
}

variable "container_image" {
  type        = string
  description = "Container image URI for Tally jobs on Cloud Run"
  default     = "gcr.io/tally-analytics-prod/tally-engine:v0.1.0"
}
