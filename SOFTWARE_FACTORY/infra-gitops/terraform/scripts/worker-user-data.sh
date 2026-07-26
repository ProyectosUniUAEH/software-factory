#!/bin/bash
# ==============================================================================
# K3S WORKER NODE SETUP
# ==============================================================================

set -e

exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "=========================================="
echo "Starting K3s Worker Node Setup..."
echo "=========================================="

K3S_VERSION="${k3s_version}"
K3S_TOKEN="${k3s_token}"
MASTER_IP="${master_ip}"

# System Update
apt-get update -y
apt-get upgrade -y
apt-get install -y curl wget jq

# Add swap to prevent OOM on small instances
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' >> /etc/sysctl.conf
sysctl vm.swappiness=10

# Get AWS instance metadata for Cluster Autoscaler node matching
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
PROVIDER_ID="aws:///$AZ/$INSTANCE_ID"
echo ">>> Provider ID: $PROVIDER_ID"

# Wait for master to be ready
echo ">>> Waiting for master node to be ready..."
sleep 60

# Install K3s Agent with AWS provider ID for Cluster Autoscaler
echo ">>> Installing K3s agent..."
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" K3S_URL="https://$MASTER_IP:6443" K3S_TOKEN="$K3S_TOKEN" sh -s - --kubelet-arg="provider-id=$PROVIDER_ID"

echo ">>> K3s worker node setup complete!"
