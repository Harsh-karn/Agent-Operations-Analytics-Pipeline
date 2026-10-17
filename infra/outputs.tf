output "raw_dataset_id" {
  description = "The ID of the raw BigQuery dataset"
  value       = google_bigquery_dataset.raw.dataset_id
}

output "analytics_dataset_id" {
  description = "The ID of the analytical BigQuery dataset"
  value       = google_bigquery_dataset.analytics.dataset_id
}

output "service_account_email" {
  description = "Email of the service account used to run scheduled pipeline jobs"
  value       = google_service_account.pipeline_runner.email
}

output "nightly_job_name" {
  description = "Name of the Cloud Run nightly grader job"
  value       = google_cloud_run_v2_job.nightly_grader.name
}

output "monthly_report_job_name" {
  description = "Name of the Cloud Run monthly report job"
  value       = google_cloud_run_v2_job.monthly_reporter.name
}
