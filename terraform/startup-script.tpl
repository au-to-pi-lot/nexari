#! /bin/bash

# Pull the Cloud SDK image
docker pull gcr.io/google.com/cloudsdktool/google-cloud-cli:stable

# Create toolbox bin directory and wrapper script for gcloud
mkdir -p /var/lib/toolbox/bin
cat > /var/lib/toolbox/bin/gcloud << 'EOF'
#!/bin/bash
docker run --rm \
  -v /var/lib/gcloud:/root/.config \
  -v /var/lib/docker/gcloud:/root/.docker \
  --network host \
  gcr.io/google.com/cloudsdktool/google-cloud-cli:stable \
  gcloud "$@"
EOF

chmod +x /var/lib/toolbox/bin/gcloud

# Add toolbox bin to PATH for all users
cat > /etc/profile.d/toolbox-path.sh << 'EOF'
export PATH=$PATH:/var/lib/toolbox/bin
EOF
chmod +x /etc/profile.d/toolbox-path.sh
source /etc/profile.d/toolbox-path.sh

# Authenticate and configure Docker
gcloud auth activate-service-account --no-user-output-enabled
gcloud auth configure-docker

# Create systemd service file
cat > /etc/systemd/system/discord-bot.service << 'EOF'
[Unit]
Description=Discord Bot Service
After=docker.service
Requires=docker.service

[Service]
Environment="HOME=/home/chronos"
ExecStartPre=/bin/bash -c '/usr/bin/docker pull gcr.io/${project_id}/${service_name}:$(gcloud secrets versions access latest --secret=active-container-tag)'
ExecStart=/bin/bash -c 'docker run --rm \
  --name discord-bot \
  -e DATABASE_URL="$(gcloud secrets versions access latest --secret=database-url)" \
  -e BOT_TOKEN="$(gcloud secrets versions access latest --secret=discord-token)" \
  -e CLIENT_ID="$(gcloud secrets versions access latest --secret=discord-client-id)" \
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
