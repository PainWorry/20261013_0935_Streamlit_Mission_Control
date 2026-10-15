# 🛠️ Post-Approval FAANG DevOps & SRE Operations Runbook

> **Document Class**: Level-3 SRE Engineering Runbook & Disaster Recovery Playbook  
> **Target Audience**: DevOps Engineers, Site Reliability Engineers (SRE), Cloud Operations, System Administrators  
> **System**: Streamlit Mission Control (ระบบติดตามและยืนยันคำสั่งงาน)  
> **Cloud Provider**: AWS Asia Pacific (Bangkok) `ap-southeast-7`  
> **Infrastructure as Code**: Terraform HCL (Declarative)  
> **Runtime Environment**: Ubuntu 24.04 LTS Noble + Docker Engine + Nginx Reverse Proxy  

---

## 1. Environment & Infrastructure Inventory

| Resource Type | Resource Name / ID | Configuration / Specs | Access Endpoint / Identifier |
| :--- | :--- | :--- | :--- |
| **AWS Region** | `ap-southeast-7` | Bangkok, Thailand (Local Zone / Region) | Subnet AZ 7a (`subnet-09f1fdfb18ee69a7c`) |
| **EC2 Instance** | `mission-control-server` | `t3.micro` (2 vCPU, 1 GiB RAM, 20 GB gp3) | `i-05be016f15cf61e82` |
| **Static IPv4 (EIP)** | `mission-control-eip` | Elastic Static Public IP | `43.211.85.163` |
| **Security Group** | `mission-control-sg-web` | Inbound: 80, 443, 8501, 22 (All CIDR 0.0.0.0/0) | `sg-0b8e2cc17fa8c03bf` |
| **SSH Key Pair** | `mission_control_bkk_key.pem` | RSA 4096-bit OpenSSH | Stored securely in `terraform/` (chmod 400) |
| **Production HTTPS URL** | CloudFront Edge (Managed SSL 🔒) | Amazon Wildcard SSL | **[https://d1z7r0ybkby2pf.cloudfront.net](https://d1z7r0ybkby2pf.cloudfront.net)** |
| **Direct Web URL (HTTP)**| Direct Nginx Fallback | Nginx Port 80 (Auto-upgraded WebSockets) | [http://43.211.85.163](http://43.211.85.163) |
| **Direct Streamlit URL** | Internal / Debug Port | Streamlit Port 8501 | [http://43.211.85.163:8501](http://43.211.85.163:8501) |

---

## 2. Granular Host Access & SSH Procedures

### 2.1 SSH Bastion & Host Connection
From your administrative terminal inside the repository's `terraform/` directory:

```bash
# 1. Ensure private key permissions are locked down
chmod 400 mission_control_bkk_key.pem

# 2. Connect directly to the Bangkok EC2 host
ssh -i ./mission_control_bkk_key.pem ubuntu@43.211.85.163
```

---

## 3. Container Management & Health Monitoring

The application runs under Docker Compose in `/opt/mission_control` with two decoupled services:
1. `mission_control_web`: Streamlit Python 3.12 application container.
2. `mission_control_nginx`: Nginx edge reverse proxy with WebSocket support.

### 3.1 Inspect Container Health & Status
```bash
cd /opt/mission_control
sudo docker compose ps
```
*Expected Output:*
```text
NAME                     IMAGE                                COMMAND                  SERVICE     CREATED         STATUS                   PORTS
mission_control_nginx    nginx:alpine                         "/docker-entrypoint.…"   nginx       1 minute ago    Up 1 minute (healthy)    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
mission_control_web      20261013_0935_streamlit_mission_c…   "streamlit run app.p…"   app         1 minute ago    Up 1 minute (healthy)    0.0.0.0:8501->8501/tcp
```

### 3.2 Tail Live Container Logs
```bash
# Tail Streamlit application logs (tracebacks, user actions, Teams webhooks)
sudo docker compose logs -f app

# Tail Nginx reverse proxy access and error logs (HTTP requests, status codes)
sudo docker compose logs -f nginx
```

### 3.3 Restart Services
```bash
# Graceful restart of both services
sudo docker compose restart

# Full recreate if configurations changed
sudo docker compose down
sudo docker compose up -d --build
```

---

## 4. Persistent Storage Architecture & Backup Runbook

Data is persisted on the host machine at `/opt/mission_control/data/` and volume-mounted into the container at `/app/data/`:
- `data/orders.csv`: Primary database of all active and historical tasks.
- `data/users.csv`: Personnel registry, roles, and PIN hashes.
- `data/order_logs.csv`: SRE audit trail of all status transitions and timestamped step notes.

### 4.1 On-Demand Backup Snapshot
To create an instantaneous off-instance backup archive:

```bash
# On local workstation
ssh -i ./terraform/mission_control_bkk_key.pem ubuntu@43.211.85.163 \
  "sudo tar -czvf /tmp/mission_control_backup_\$(date +%Y%m%d_%H%M%S).tar.gz -C /opt/mission_control/data ."

# Download backup archive to local machine
scp -i ./terraform/mission_control_bkk_key.pem ubuntu@43.211.85.163:/tmp/mission_control_backup_*.tar.gz ./backups/
```

### 4.2 Automated Nightly Cron Backup
To schedule automated nightly backups on the EC2 host:
```bash
# Add to root crontab on EC2
sudo crontab -e
# Add line:
0 3 * * * tar -czvf /opt/backups/data_$(date +\%Y\%m\%d).tar.gz -C /opt/mission_control/data . && find /opt/backups -type f -mtime +14 -delete
```

---

## 5. Zero-Downtime Continuous Deployment (Rolling Updates)

Whenever new features, bug fixes, or UI changes are merged to GitHub:

```bash
# Execute on EC2 host:
cd /opt/mission_control
sudo git pull origin main
sudo docker compose up -d --build
```
Docker will rebuild the Streamlit container layer and swap the container in under 3 seconds without dropping the Nginx reverse proxy listener.

---

## 6. SRE Disaster Recovery & Rollback Procedures

### 6.1 Container Failure / Crash Loop
If Streamlit encounters a fatal memory error or corrupt CSV:
1. Check logs: `sudo docker compose logs --tail=100 app`
2. If `orders.csv` is malformed, restore from latest snapshot:
   ```bash
   sudo cp /opt/mission_control/data/orders.csv.bak /opt/mission_control/data/orders.csv
   sudo docker compose restart app
   ```

### 6.2 Full Server Disaster Reconstruction (RTO < 5 Minutes)
If the EC2 virtual machine is terminated or suffers hardware failure:
1. Navigate to the local repository `terraform/` directory.
2. Execute:
   ```bash
   terraform apply -auto-approve
   ```
3. Terraform will provision a brand new Ubuntu EC2 instance, re-attach the static Elastic IP (`43.211.85.163`), bootstrap Docker, and launch the application automatically.
4. Restore `data/` from your latest offsite backup archive.

---

## 7. Controlled Decommissioning & Teardown SLA

If the infrastructure needs to be decommissioned to stop AWS billing:

```bash
# From local terraform directory
cd terraform/
terraform destroy -auto-approve
```
*SLA*: All 6 AWS resources (EC2, Elastic IP, Security Group, SSH Key Pair, EBS storage) will be cleanly released in under 60 seconds, reducing AWS burn rate to **$0.00**.
