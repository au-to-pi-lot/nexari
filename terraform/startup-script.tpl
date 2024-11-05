#cloud-config

write_files:
- path: /etc/systemd/system/discord-bot.service
  permissions: 0644
  owner: root
  content: |
    [Unit]
    Description=Discord Bot Service
    After=docker.service
    Requires=docker.service

    [Service]
    Environment="HOME=/home/chronos"
    ExecStartPre=/usr/bin/docker-credential-gcr configure-docker
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

runcmd:
- systemctl daemon-reload
- systemctl enable discord-bot.service
- systemctl start discord-bot.service
