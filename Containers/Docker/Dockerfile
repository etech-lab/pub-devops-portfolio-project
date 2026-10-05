FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=us-east-1 \
    SSH_USER=webtester \
    SSH_PUBLIC_KEY_SECRET_NAME=websitetester/ssh/webtester-public-key

WORKDIR /websitetester_app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-server ca-certificates curl wget jq awscli \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ${SSH_USER} \
    && mkdir -p /var/run/sshd /home/${SSH_USER}/.ssh \
    && chown -R ${SSH_USER}:${SSH_USER} /home/${SSH_USER}/.ssh \
    && chmod 700 /home/${SSH_USER}/.ssh

RUN sed -ri 's/^#?PasswordAuthentication\s+.*/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -ri 's/^#?PubkeyAuthentication\s+.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config \
    && echo 'AllowUsers webtester' >> /etc/ssh/sshd_config

COPY requirements.txt /websitetester_app/requirements.txt
RUN pip install --no-cache-dir -r /websitetester_app/requirements.txt

COPY site_test /websitetester_app/site_test
COPY scripts /websitetester_app/scripts
COPY Containers/Docker/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
