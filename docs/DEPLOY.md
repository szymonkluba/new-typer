# Deploying Typer on OCI VM

- **Domain:** skijtyper.pl
- **VM IP:** 158.180.16.100

## Prerequisites

- OCI Ubuntu VM (free tier works)
- SSH access to the VM
- Git repository accessible from the VM
- Domain DNS A record pointing to the VM IP

## One-time VM setup

### 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu
# Log out and back in for group change to take effect
```

### 2. Install nginx and certbot

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 3. Configure DNS

Add an A record for your domain pointing to the VM:

| Type | Name | Value |
|------|------|-------|
| A | skijtyper.pl | 158.180.16.100 |

Wait for DNS propagation (check with `dig skijtyper.pl`).

### 4. Open firewall ports

OCI VMs have two layers of firewall — both must allow ports 80 and 443.

**OCI Security List (VCN level):**
- Go to Networking > Virtual Cloud Networks > your VCN > Security Lists
- Add ingress rules:
  - Source `0.0.0.0/0`, Protocol TCP, Destination Port `80`
  - Source `0.0.0.0/0`, Protocol TCP, Destination Port `443`

**iptables (VM level):**

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### 5. Clone the repo and configure

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

### 6. Obtain SSL certificate

First, set up a temporary nginx config so certbot can verify domain ownership:

```bash
sudo tee /etc/nginx/sites-available/typer <<'CONF'
server {
    listen 80;
    server_name skijtyper.pl;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'setting up...';
        add_header Content-Type text/plain;
    }
}
CONF

sudo mkdir -p /var/www/certbot
sudo ln -sf /etc/nginx/sites-available/typer /etc/nginx/sites-enabled/typer
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Now obtain the certificate:

```bash
sudo certbot certonly --webroot -w /var/www/certbot -d skijtyper.pl
```

### 7. Install the full nginx config

```bash
sudo cp nginx/nginx.conf /etc/nginx/sites-available/typer
sudo nginx -t
sudo systemctl reload nginx
```

Certbot auto-renewal is set up automatically via systemd timer. Verify with:

```bash
sudo systemctl list-timers | grep certbot
```

### 8. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

The app should now be accessible at `https://skijtyper.pl`.

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

**Ports not reachable from outside:**
- Check OCI Security List has port 80 + 443 ingress rules
- Check iptables: `sudo iptables -L INPUT -n --line-numbers`
- Check nginx is running: `sudo systemctl status nginx`

**SSL certificate renewal:**
```bash
sudo certbot renew --dry-run
```

**Database reset (if needed):**
```bash
docker compose down
docker volume rm typer_db-data
docker compose up -d
```
This destroys all data — the app creates fresh tables on startup.
