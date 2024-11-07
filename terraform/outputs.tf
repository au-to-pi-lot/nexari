
output "database_connection" {
  value     = google_sql_database_instance.instance.connection_name
  sensitive = true
}
