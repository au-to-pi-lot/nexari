#! /bin/bash

# Create persistent directory for docker config
mkdir -p /var/lib/docker/auth
chmod 755 /var/lib/docker/auth

# Create Docker credential helper config
cat > /var/lib/docker/auth/config.json << 'EOF'
{
  "credHelpers": {
    "gcr.io": "gcloud",
    "us.gcr.io": "gcloud", 
    "eu.gcr.io": "gcloud",
    "asia.gcr.io": "gcloud",
    "staging-k8s.gcr.io": "gcloud",
    "marketplace.gcr.io": "gcloud"
  }
}
EOF

# Make docker use the persistent auth config
mkdir -p /home/chronos/.docker
ln -sf /var/lib/docker/auth/config.json /home/chronos/.docker/config.json
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
