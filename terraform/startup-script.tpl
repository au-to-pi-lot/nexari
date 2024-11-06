#! /bin/bash

# Pull the Cloud SDK image
docker pull gcr.io/google.com/cloudsdktool/google-cloud-cli:stable

# Configure Docker authentication using Cloud SDK
docker run --rm \
  -v /home/chronos/.docker:/root/.docker \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gcr.io/google.com/cloudsdktool/google-cloud-cli:stable \
  gcloud auth configure-docker -q

chown -R chronos:chronos /home/chronos/.docker

# Create systemd service file
cat > /etc/systemd/system/discord-bot.service << 'EOF'
[Unit]
Description=Discord Bot Service
After=docker.service
Requires=docker.service

[Service]
Environment="HOME=/home/chronos"
ExecStartPre=/bin/bash -c '/usr/bin/docker pull gcr.io/${project_id}/${service_name}:$(docker run --rm gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=active-container-tag)'
ExecStart=/bin/bash -c 'docker run --rm \
  --name discord-bot \
  -e DATABASE_URL="$(docker run --rm gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=database-url)" \
  -e BOT_TOKEN="$(docker run --rm gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=discord-token)" \
  -e CLIENT_ID="$(docker run --rm gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=discord-client-id)" \
  gcr.io/${project_id}/${service_name}:$(docker run --rm gcr.io/google.com/cloudsdktool/google-cloud-cli:stable gcloud secrets versions access latest --secret=active-container-tag)'
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
