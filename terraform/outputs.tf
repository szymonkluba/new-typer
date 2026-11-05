output "instance_id" {
  description = "OCID of the compute instance"
  value       = oci_core_instance.typer.id
}

output "public_ip" {
  description = "Reserved public IP address"
  value       = oci_core_public_ip.typer.ip_address
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh opc@${oci_core_public_ip.typer.ip_address}"
}

output "next_steps" {
  description = "Post-apply steps"
  value       = <<-EOT
    1. Wait for cloud-init: ssh opc@${oci_core_public_ip.typer.ip_address} 'cloud-init status --wait'
    2. Point DNS A record for skijtyper.pl to ${oci_core_public_ip.typer.ip_address}
    3. Run certbot: sudo certbot certonly --webroot -w /var/www/certbot -d skijtyper.pl
    4. Clone repo, create .env, run deploy.sh — see docs/DEPLOY.md
  EOT
}
