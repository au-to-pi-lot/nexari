output "instance_ip" {
  value = google_compute_instance.bot.network_interface[0].access_config[0].nat_ip
  description = "The public IP of the Discord bot instance"
}

output "database_connection" {
  value     = google_sql_database_instance.instance.connection_name
  sensitive = true
}
