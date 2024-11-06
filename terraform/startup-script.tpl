#! /bin/bash

# Configure docker credential helper for GCR
mkdir -p /home/chronos/.docker
cat > /home/chronos/.docker/config.json << 'EOF'
{
  "credHelpers": {
    "gcr.io": "gcr"
  }
}
EOF
chown -R chronos:chronos /home/chronos/.docker

# Create systemd service file
cat > /etc/systemd/system/discord-bot.service << 'EOF'
[Unit]
Description=Discord Bot Service
After=docker.service
Requires=docker.service

[Service]
Environment="HOME=/home/chronos"
ExecStartPre=/usr/bin/docker pull gcr.io/${project_id}/${service_name}:latest
ExecStart=/bin/bash -c 'docker run --rm \
  --name discord-bot \
  -e DATABASE_URL="$(gcloud secrets versions access latest --secret=database-url)" \
  -e BOT_TOKEN="$(gcloud secrets versions access latest --secret=discord-token)" \
  -e CLIENT_ID="$(gcloud secrets versions access latest --secret=discord-client-id)" \
  gcr.io/${project_id}/${service_name}:latest'
ExecStop=/usr/bin/docker stop discord-bot
Restart=always
RestartSec=10
User=chronos
Group=chronos

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable discord-bot.service
systemctl start discord-bot.service
