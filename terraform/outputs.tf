output "cloud_run_url" {
  value = google_cloud_run_v2_service.default.uri
}

output "database_connection" {
  value     = google_sql_database_instance.instance.connection_name
  sensitive = true
}
