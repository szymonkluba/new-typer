resource "oci_core_vcn" "typer" {
  compartment_id = var.compartment_id
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "typer-vcn"
  dns_label      = "typervcn"
}

resource "oci_core_internet_gateway" "typer" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.typer.id
  display_name   = "typer-igw"
  enabled        = true
}

resource "oci_core_route_table" "typer" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.typer.id
  display_name   = "typer-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.typer.id
  }
}

resource "oci_core_security_list" "typer" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.typer.id
  display_name   = "typer-sl"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6" # TCP
    stateless = false
    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6"
    stateless = false
    tcp_options {
      min = 80
      max = 80
    }
  }

  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6"
    stateless = false
    tcp_options {
      min = 443
      max = 443
    }
  }

  # ICMP for path MTU discovery
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "1" # ICMP
    stateless = false
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    source    = "10.0.0.0/16"
    protocol  = "1"
    stateless = false
    icmp_options {
      type = 3
    }
  }
}

resource "oci_core_subnet" "typer" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.typer.id
  cidr_block                 = "10.0.1.0/24"
  display_name               = "typer-public-subnet"
  dns_label                  = "typerpub"
  route_table_id             = oci_core_route_table.typer.id
  security_list_ids          = [oci_core_security_list.typer.id]
  prohibit_public_ip_on_vnic = false
}
