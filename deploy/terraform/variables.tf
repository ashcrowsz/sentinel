variable "project" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "github_repo" {
  description = "owner/name allowed to impersonate the CI service account"
  type        = string
}

output "registry" {
  value = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.images.repository_id}"
}

output "k3s_ip" {
  value = google_compute_instance.k3s.network_interface[0].access_config[0].nat_ip
}
