terraform {
  backend "s3" {
    bucket         = "vycescore-terraform-state"
    key            = "sandbox/terraform.tfstate"
    region         = "af-south-1"
    encrypt        = true
    dynamodb_table = "vycescore-terraform-locks"
  }
}
