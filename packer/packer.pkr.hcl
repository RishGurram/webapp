packer {
  required_plugins {
    amazon = {
      version = ">= 0.0.2"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "ami_users" {
  type    = list(string)
  default = ["379939392295", "641492930170"]
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "source_ami" {
  type    = string
  default = "ami-0dfcb1ef8550277af"
}

variable "instance_type" {
  type    = string
  default = "t2.micro"
}

variable "ssh_username" {
  type    = string
  default = "ec2-user"
}

variable "subnet_id" {
  type    = string
  default = "subnet-000f5ac45adaf0e3a"
}

variable "vpc_id" {
  type    = string
  default = "vpc-03adba7dd8dcf6669"
}

variable "ami_name" {
  type    = string
  default = "webapp-ami"
}
variable "environment" {
  type    = string
  default = "dev"
}

source "amazon-ebs" "webapp-ami" {
  ami_name      = "${var.ami_name}"
  ami_users     = "${var.ami_users}"
  instance_type = "${var.instance_type}"
  region        = "${var.region}"
  source_ami    = "${var.source_ami}"
  ssh_username  = "${var.ssh_username}"
  subnet_id     = "${var.subnet_id}"
  tags = {
    Name        = "${var.ami_name}"
    Environment = "${var.environment}"
  }
  vpc_id = "${var.vpc_id}"

  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    delete_on_termination = true
  }
}

build {
  sources = [
    "source.amazon-ebs.webapp-ami"
  ]
  provisioner "file" {
    source      = "_init_.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "database.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "main.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "models.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "schema.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "test_main.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "utils.py"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "requirements.txt"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "webapp.service"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "nginx.conf"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "requirements.txt"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "webapp.service"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "nginx.conf"
    destination = "/home/ec2-user/"
  }
  provisioner "file" {
    source      = "database.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "main.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "models.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "schema.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "test_main.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "utils.py"
    destination = "~"
  }
  provisioner "file" {
    source      = "requirements.txt"
    destination = "~"
  }
  provisioner "file" {
    source      = "webapp.service"
    destination = "~"
  }
  provisioner "file" {
    source      = "nginx.conf"
    destination = "~"
  }


  provisioner "shell" {
    script = "packer/provision.sh"
  }
}