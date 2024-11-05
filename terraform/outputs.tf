output "instance_ip" {
  value       = google_compute_address.static_ip.address
  description = "The static IP address of the Discord bot instance"
}

output "database_connection" {
  value     = google_sql_database_instance.instance.connection_name
  sensitive = true
}
