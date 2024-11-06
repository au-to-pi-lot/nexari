#! /bin/bash

# Pull the Cloud SDK image
docker pull gcr.io/google.com/cloudsdktool/google-cloud-cli:stable

# Create systemd service file
cat > /etc/systemd/system/discord-bot.service << 'EOF'
[Unit]
Description=Discord Bot Service
After=docker.service
Requires=docker.service

[Service]
Environment="HOME=/home/chronos"
ExecStartPre=/bin/bash -c '/usr/bin/docker pull gcr.io/${project_id}/${service_name}:$(docker run --rm --network host gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=active-container-tag)'
ExecStart=/bin/bash -c 'docker run --rm \
  --name discord-bot \
  -e DATABASE_URL="$(docker run --rm --network host gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=database-url)" \
  -e BOT_TOKEN="$(docker run --rm --network host gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=discord-token)" \
  -e CLIENT_ID="$(docker run --rm --network host gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=discord-client-id)" \
  gcr.io/${project_id}/${service_name}:$(gcloud secrets versions access latest --secret=active-container-tag)'
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
