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
      -e DATABASE_URL="${database_url}" \
      -e BOT_TOKEN="${bot_token}" \
      -e CLIENT_ID="${client_id}" \
      gcr.io/${project_id}/${service_name}:${active_container_tag}'
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