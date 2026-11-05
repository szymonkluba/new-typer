variable "tenancy_ocid" {
  description = "OCI tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI user OCID"
  type        = string
}

variable "compartment_id" {
  description = "Compartment OCID to create resources in"
  type        = string
}

variable "fingerprint" {
  description = "API key fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API signing private key"
  type        = string
}

variable "region" {
  description = "OCI home region (e.g. eu-frankfurt-1)"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key for VM access"
  type        = string
}

variable "instance_shape" {
  description = "Compute instance shape"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "Number of OCPUs for the instance"
  type        = number
  default     = 1
}

variable "instance_memory_in_gbs" {
  description = "Memory in GB for the instance"
  type        = number
  default     = 6
}

variable "boot_volume_size_in_gbs" {
  description = "Boot volume size in GB"
  type        = number
  default     = 50
}
