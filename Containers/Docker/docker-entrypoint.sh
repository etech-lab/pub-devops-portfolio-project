#!/usr/bin/env bash
set -euo pipefail

SSH_USER="${SSH_USER:-webtester}"
SSH_PUBLIC_KEY_SECRET_NAME="${SSH_PUBLIC_KEY_SECRET_NAME:-websitetester/ssh/webtester-public-key}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

export AWS_DEFAULT_REGION

mkdir -p "/home/${SSH_USER}/.ssh"
chmod 700 "/home/${SSH_USER}/.ssh"

python - <<'PY'
import os
import boto3

secret_name = os.environ["SSH_PUBLIC_KEY_SECRET_NAME"]
region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ssh_user = os.environ.get("SSH_USER", "webtester")
out_path = f"/home/{ssh_user}/.ssh/authorized_keys"

client = boto3.client("secretsmanager", region_name=region)
resp = client.get_secret_value(SecretId=secret_name)
value = resp.get("SecretString", "").strip()

if not value:
    raise RuntimeError(f"Secret {secret_name} is empty")

with open(out_path, "w", encoding="utf-8") as f:
    f.write(value + "\n")
PY

chmod 600 "/home/${SSH_USER}/.ssh/authorized_keys"
chown -R "${SSH_USER}:${SSH_USER}" "/home/${SSH_USER}/.ssh"

ssh-keygen -A

{
    echo "#!/usr/bin/env bash"
    [[ -n "${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI:-}" ]] && printf 'export AWS_CONTAINER_CREDENTIALS_RELATIVE_URI=%q\n' "${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}"
    [[ -n "${AWS_CONTAINER_CREDENTIALS_FULL_URI:-}" ]] && printf 'export AWS_CONTAINER_CREDENTIALS_FULL_URI=%q\n' "${AWS_CONTAINER_CREDENTIALS_FULL_URI}"
    [[ -n "${AWS_CONTAINER_AUTHORIZATION_TOKEN:-}" ]] && printf 'export AWS_CONTAINER_AUTHORIZATION_TOKEN=%q\n' "${AWS_CONTAINER_AUTHORIZATION_TOKEN}"
    [[ -n "${AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE:-}" ]] && printf 'export AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE=%q\n' "${AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE}"
    printf 'export AWS_REGION=%q\n' "${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
    printf 'export AWS_DEFAULT_REGION=%q\n' "${AWS_DEFAULT_REGION:-us-east-1}"
} >/etc/profile.d/ecs-task-role.sh
chmod 644 /etc/profile.d/ecs-task-role.sh

cat >/home/${SSH_USER}/.bash_profile <<'EOF'
if [ -f /etc/profile ]; then
    . /etc/profile
fi

if [ -f /etc/profile.d/ecs-task-role.sh ]; then
    . /etc/profile.d/ecs-task-role.sh
fi

if [[ $- == *i* ]] && [[ -z "${WEBSITETESTER_AUTORUN_DONE:-}" ]]; then
    export WEBSITETESTER_AUTORUN_DONE=1
    if [ -d /websitetester_app ]; then
        cd /websitetester_app || true
    fi
    echo "[websitetester] Running website tester app..."
    python -m site_test || echo "[websitetester] App exited with status $?"
fi
EOF
chown ${SSH_USER}:${SSH_USER} /home/${SSH_USER}/.bash_profile
chmod 644 /home/${SSH_USER}/.bash_profile

exec /usr/sbin/sshd -D -e
