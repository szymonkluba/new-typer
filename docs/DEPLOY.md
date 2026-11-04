# Deploying Typer on OCI VM

## Prerequisites

- OCI Ubuntu VM (free tier works)
- SSH access to the VM
- Git repository accessible from the VM

## One-time VM setup

### 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu
# Log out and back in for group change to take effect
```

### 2. Install nginx

```bash
sudo apt-get install -y nginx
```

### 3. Open firewall ports

OCI VMs have two layers of firewall — both must allow port 80.

**OCI Security List (VCN level):**
- Go to Networking > Virtual Cloud Networks > your VCN > Security Lists
- Add an ingress rule: Source `0.0.0.0/0`, Protocol TCP, Destination Port `80`

**iptables (VM level):**

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
```

### 4. Clone the repo and configure

```bash
cd /home/ubuntu
git clone <your-repo-url> typer
cd typer
cp .env.example .env
```

Generate a secret key and edit `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and paste it as the SECRET_KEY value in .env
nano .env
```

### 5. Configure nginx

```bash
sudo cp nginx/nginx.conf /etc/nginx/sites-available/typer
sudo ln -sf /etc/nginx/sites-available/typer /etc/nginx/sites-enabled/typer
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

The app should now be accessible at `http://<your-vm-ip>`.

## Ongoing deployment

SSH into the VM and run:

```bash
cd /home/ubuntu/typer
./deploy.sh
```

This pulls the latest code, rebuilds the Docker image, and restarts the container.

## Backup

The SQLite database lives in a Docker named volume. To back it up:

```bash
docker cp typer-app:/data/typer.db ./backup-$(date +%Y%m%d).db
```

## Logs

```bash
# Application logs
docker compose logs -f app

# Last 100 lines
docker compose logs --tail=100 app

# nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Troubleshooting

**Container won't start:**
```bash
docker compose logs app
```

**Health check failing:**
```bash
curl -v http://localhost:8000/health
```

**Port 80 not reachable from outside:**
- Check OCI Security List has port 80 ingress rule
- Check iptables: `sudo iptables -L INPUT -n --line-numbers`
- Check nginx is running: `sudo systemctl status nginx`

**Database reset (if needed):**
```bash
docker compose down
docker volume rm typer_db-data
docker compose up -d
```
This destroys all data — the app creates fresh tables on startup.
