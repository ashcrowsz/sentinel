terraform {
  required_version = ">= 1.7"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
  backend "gcs" {
    bucket = "sentinel-tfstate"
    prefix = "prod"
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

locals {
  services = [
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iamcredentials.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)
  service  = each.value
}

resource "google_compute_network" "vpc" {
  name                    = "sentinel"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "sentinel-${var.region}"
  ip_cidr_range = "10.10.0.0/24"
  network       = google_compute_network.vpc.id
  region        = var.region
}

resource "google_compute_firewall" "https_in" {
  name          = "sentinel-https-in"
  network       = google_compute_network.vpc.name
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["k3s"]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
}

resource "google_artifact_registry_repository" "images" {
  repository_id = "sentinel"
  location      = var.region
  format        = "DOCKER"
  cleanup_policies {
    id     = "keep-last-20"
    action = "KEEP"
    most_recent_versions { keep_count = 20 }
  }
}

resource "google_service_account" "node" {
  account_id   = "sentinel-node"
  display_name = "k3s node"
}

resource "google_project_iam_member" "node_secret_access" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.node.email}"
}

resource "google_compute_instance" "k3s" {
  name         = "sentinel-k3s"
  machine_type = var.machine_type
  zone         = "${var.region}-b"
  tags         = ["k3s"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 50
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main.id
    access_config {}
  }

  service_account {
    email  = google_service_account.node.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = file("${path.module}/k3s-bootstrap.sh")
}

module "wif" {
  source      = "./modules/wif"
  project     = var.project
  github_repo = var.github_repo
}
