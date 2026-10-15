#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "========================================================"
echo "Starting Mission Control EC2 Cloud-Init Bootstrap"
echo "Timestamp: $(date)"
echo "========================================================"

# 1. Update OS packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git

# 2. Install Official Docker Community Edition
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# 3. Setup Project Directory & Clone Git Repository
mkdir -p /opt/mission_control
cd /opt/mission_control

echo "Cloning latest repository from GitHub..."
git clone https://github.com/PainWorry/20261013_0935_Streamlit_Mission_Control.git .

# 4. Inject Production Secrets
mkdir -p .streamlit
cat << 'SECRETS_EOF' > .streamlit/secrets.toml
${secrets_content}
SECRETS_EOF

# 5. Build and Run Docker Containers
echo "Building and launching Docker containers via docker compose..."
docker compose up -d --build

# 6. Verify Container Health
sleep 10
docker compose ps

echo "========================================================"
echo "Mission Control EC2 Bootstrap Completed Successfully!"
echo "Timestamp: $(date)"
echo "========================================================"
