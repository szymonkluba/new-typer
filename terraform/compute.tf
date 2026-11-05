resource "oci_core_instance" "typer" {
  compartment_id      = var.compartment_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "typer-vm"
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.oracle_linux.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.typer.id
    assign_public_ip = false
    display_name     = "typer-vnic"
  }

  metadata = {
    ssh_authorized_keys = file(var.ssh_public_key_path)
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Reserved public IP — persists across instance recreation for DNS stability
data "oci_core_vnic_attachments" "typer" {
  compartment_id = var.compartment_id
  instance_id    = oci_core_instance.typer.id
}

data "oci_core_private_ips" "typer" {
  vnic_id = data.oci_core_vnic_attachments.typer.vnic_attachments[0].vnic_id
}

resource "oci_core_public_ip" "typer" {
  compartment_id = var.compartment_id
  display_name   = "typer-reserved-ip"
  lifetime       = "RESERVED"
  private_ip_id  = data.oci_core_private_ips.typer.private_ips[0].id
}
