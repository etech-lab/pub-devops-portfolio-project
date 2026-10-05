# Website Tester - DevOps Portfolio Project

> **Note:** This is a portfolio project designed to demonstrate DevOps engineering skills, infrastructure automation, and CI/CD practices. It is not intended for production use.

## Overview

This is a basic application for URL validation. The deployment uses Docker, ECS Fargate, RDS, NLB, and AWS developer tools such as CodePipeline, CodeBuild, and CodeStar. For infrastructure as code, CloudFormation is used to deploy both bootstrap infrastructure components and application stacks. Two pipelines were built: one for infrastructure and one for the application components. Currently, there is no GUI frontend, and the application is accessed through SSH using the NLB DNS.

## Project Goals

This project is designed to show the progression of DevOps skills rather than present a final solution. It is broken down into three iterations, with Iteration 1 focused on developing an end-to-end application using cloud-native services, infrastructure as code, and automated CI/CD pipelines. Some design decisions were intentionally made with later improvements in mind so the architecture could evolve over time, but this is still a portfolio project. The goal is to be production minded while balancing effort and cost constraints.

## Iteration Structure

This project is organized into three progressive iterations, each building upon the previous:

### Iteration 1: ECS Architecture & CI/CD Deployment

Iteration 1 establishes the foundation: a containerized application deployed on ECS Fargate with a PostgreSQL RDS backend, traffic routed through a Network Load Balancer, and two separate CI/CD pipelines for infrastructure and application changes. Infrastructure and application deployments are separated into dedicated CloudFormation stacks and CodePipeline workflows, allowing teams to manage platform and service changes independently.

The architecture uses AWS Secrets Manager to store database credentials and SSH access keys, enabling secure credential retrieval without hardcoding secrets into code or templates. Application access is currently managed through SSH directly into running containers using stored key material. By the end of Iteration 1, the complete deployment pipeline is functional and documented. Infrastructure changes, database migrations, and application deployments all flow through automated pipelines, demonstrating repeatable CI/CD discipline and infrastructure-as-code practices.

### Iteration 2: EKS Architecture & Hosted Website with web UI frontend

Iteration 2 moves the platform from ECS Fargate to an EKS based deployment backed by EC2 worker nodes, expanding the project from a container service model into Kubernetes orchestration. This phase also introduces a hosted web UI so the application can be accessed through a browser instead of SSH based container access, with a public domain used for live validation. As part of the security evolution, database access transitions from static Secrets Manager credentials to a token based authentication model.

### Iteration 3: CDN, API Layer, and Terraform Integration

Iteration 3 adds a lightweight delivery and reporting layer on top of the existing platform rather than rebuilding the core infrastructure. CloudFront is introduced as a CDN to provide a cleaner public entry point, while API Gateway supports a small read-only API for exposing stored website test results and summary data from the PostgreSQL backend. Terraform is introduced selectively for this CDN and API layer, while the core application infrastructure remains managed through CloudFormation.

## Tech Stack

### AWS Services

- **Compute**: ECS (Fargate), EC2
- **Containers**: ECR (Elastic Container Registry)
- **Database**: RDS (PostgreSQL)
- **Networking**: VPC, Network Load Balancer (NLB), Security Groups
- **Infrastructure as Code**: CloudFormation
- **CI/CD**: CodePipeline, CodeBuild
- **Security**: Secrets Manager, IAM, Systems Manager (SSM)
- **Notifications**: SNS

### Development & Tools

- **Language**: Python 3.12
- **Containerization**: Docker
- **Version Control**: Git, GitHub
- **Linting**: cfn-lint
- **CLI Tools**: AWS CLI, psql

### Architecture Patterns

- Infrastructure as Code (IaC)
- Containerized microservices
- Multi-stage CI/CD pipelines
- Secrets management with AWS Secrets Manager
- Multi-AZ deployment for high availability

## Documentation

Detailed documentation for each iteration, including architecture diagrams, deployment steps, and design decisions, can be found in the [`docs/iterations/`](docs/iterations/) directory.

## Prerequisites

To deploy or replicate this project, you'll need:

### Required

- **AWS Account** with appropriate permissions for:
  - CloudFormation stack creation
  - ECS, ECR, RDS, VPC, and IAM resource management
  - CodePipeline and CodeBuild access
- **AWS CLI** installed and configured with credentials
- **Git** for cloning the repository
- **SSH key pair** for ECS task access (public key stored in Secrets Manager)

### Optional (for local development/testing)

- **Docker** (for building and testing container images locally)
- **Python 3.12+** (for running the application locally)
- **PostgreSQL client (psql)** (for direct database access)
- **cfn-lint** (for CloudFormation template validation)

### Knowledge Requirements

- Basic understanding of AWS services (ECS, CloudFormation, RDS)
- Familiarity with Docker and containerization concepts
- Understanding of CI/CD pipeline workflows
- Basic knowledge of networking (VPCs, subnets, security groups)

## Disclaimer

This repository has been sanitized for public sharing. Sensitive information such as AWS account IDs and email addresses have been removed or replaced with placeholder values in CloudFormation templates and configuration files. Screenshots may contain account-specific information, which is acceptable for demonstration purposes.
