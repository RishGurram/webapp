SHELL := /bin/bash
VENV_NAME=venv

#
.EXPORT_ALL_VARIABLES:

POSTGRES_USER ?= webapp
POSTGRES_PASSWORD ?= webapp
POSTGRES_HOST ?= 127.0.0.1
POSTGRES_PORT ?= 5432
POSTGRES_DB ?= webapp
DATABASE_URL?= postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)

# =============================================================================

init:
	packer init packer

fmt:
	packer fmt packer
	
validate: fmt
	packer validate packer

build: init validate
	packer build packer/packer.pkr.hcl
