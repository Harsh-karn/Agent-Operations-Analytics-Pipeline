terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. BigQuery Datasets
resource "google_bigquery_dataset" "tally_raw" {
  dataset_id                  = var.dataset_raw_name
  friendly_name               = "Tally Raw Telemetry"
  description                 = "Raw agent runs, events, approvals, incidents, and contact logs"
  location                    = var.region
  default_table_expiration_ms = null

  labels = {
    environment = "production"
    platform    = "tally"
  }
}

resource "google_bigquery_dataset" "tally_analytics" {
  dataset_id                  = var.dataset_views_name
  friendly_name               = "Tally Analytical Views & Defensible Grades"
  description                 = "Versioned views: ledger_monthly, cost_per_run, team_signals, maturity_grade"
  location                    = var.region
  default_table_expiration_ms = null

  labels = {
    environment = "production"
    platform    = "tally"
  }
}

# 2. Service Account with Least Privilege
resource "google_service_account" "tally_runner" {
  account_id   = "tally-pipeline-runner"
  display_name = "Tally Pipeline Service Account"
  description  = "Executes nightly maturity grading, views refresh, and monthly reports"
}

resource "google_project_iam_member" "bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.tally_runner.email}"
}

resource "google_bigquery_dataset_iam_member" "raw_editor" {
  dataset_id = google_bigquery_dataset.tally_raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.tally_runner.email}"
}

resource "google_bigquery_dataset_iam_member" "analytics_editor" {
  dataset_id = google_bigquery_dataset.tally_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.tally_runner.email}"
}

# 3. Cloud Run Jobs (Serverless Execution)
resource "google_cloud_run_v2_job" "nightly_grader" {
  name     = "tally-nightly-grader"
  location = var.region

  template {
    template {
      service_account = google_service_account.tally_runner.email
      containers {
        image = var.container_image
        command = ["python", "-m", "tally.grading", "--execute-nightly"]
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        resources {
          limits = {
            cpu    = "2000m"
            memory = "2Gi"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "monthly_reporter" {
  name     = "tally-monthly-reporter"
  location = var.region

  template {
    template {
      service_account = google_service_account.tally_runner.email
      containers {
        image = var.container_image
        command = ["python", "-m", "tally.reports.monthly"]
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        resources {
          limits = {
            cpu    = "2000m"
            memory = "2Gi"
          }
        }
      }
    }
  }
}

# 4. Cloud Scheduler Triggers
resource "google_cloud_scheduler_job" "nightly_trigger" {
  name             = "tally-nightly-grader-trigger"
  description      = "Fires daily at 2:00 AM UTC to refresh views and score team maturity"
  schedule         = "0 2 * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.nightly_grader.name}:run"

    oauth_token {
      service_account_email = google_service_account.tally_runner.email
    }
  }
}

resource "google_cloud_scheduler_job" "monthly_trigger" {
  name             = "tally-monthly-report-trigger"
  description      = "Fires 1st of every month at 6:00 AM UTC to compile executive report"
  schedule         = "0 6 1 * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.monthly_reporter.name}:run"

    oauth_token {
      service_account_email = google_service_account.tally_runner.email
    }
  }
}
