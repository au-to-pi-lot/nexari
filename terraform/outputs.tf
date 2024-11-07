
output "database_connection" {
  description = "The connection name for the Cloud SQL instance"
  value       = google_sql_database_instance.instance.connection_name
  sensitive   = true
}
