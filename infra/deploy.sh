#!/bin/bash
# TruthMachine EC2 Deployment Script
set -e

# Terminology: The Factum Atlas / OSNC / The Vault
echo "Initializing TruthMachine Cloud Infrastructure..."

# 1. Provision Infrastructure
cd openclaw/terraform
terraform init
terraform apply -auto-approve

# 2. Extract Instance IP
INSTANCE_IP=$(terraform output -raw instance_public_ip)
echo "Instance provisioned at: $INSTANCE_IP"

# 3. Deploy Pipeline to EC2
# Note: This assumes SSH access is configured in terraform
echo "Syncing pipeline and data to EC2..."
ssh -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "mkdir -p ~/truthmachine"
scp -r ../../../pipeline ubuntu@$INSTANCE_IP:~/truthmachine/
scp -r ../../../data ubuntu@$INSTANCE_IP:~/truthmachine/
scp ../../../.env ubuntu@$INSTANCE_IP:~/truthmachine/pipeline/

# 4. Start Docker environment on EC2
echo "Starting TruthMachine Docker environment on EC2..."
ssh ubuntu@$INSTANCE_IP "cd ~/truthmachine/pipeline && docker-compose up -d"

echo "Deployment complete! TruthMachine is running on $INSTANCE_IP"
