# Infrastructure setup for application deployment

Reusable template for deploying and tearing down application infrastructure.

## Deployment Order

Bootstrap templates (`btstrp-*`) are one-time foundation stacks that should be deployed before regular infrastructure pipeline stacks.

Deploy stacks in this order to satisfy dependencies:

### 1. Deploy DB/Postgres IAM Bootstrap (one-time)
```bash
aws cloudformation create-stack \
  --stack-name btstrp-db-postgres-iam-stack \
  --template-body file://cfn-infrastructure/btstrp-db-postgres-iam-roles.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Deploy VPC (if not already deployed)
```bash
aws cloudformation create-stack \
  --stack-name devops-vpc-stack \
  --template-body file://cfn-infrastructure/vpc-network.yaml
```

### 3. Deploy RDS Database
```bash
aws cloudformation create-stack \
  --stack-name devops-rds \
  --template-body file://cfn-infrastructure/postgres-rds-cfn.yaml \
  --parameters \
    ParameterKey=VpcStackName,ParameterValue=devops-vpc-stack \
    ParameterKey=DBPassword,ParameterValue=YourSecurePassword123
```

### 4. Store Credentials in Secrets Manager
After RDS is deployed, store the database credentials in Secrets Manager so the application can retrieve them securely without hardcoding passwords.

```bash
aws secretsmanager create-secret \
  --name rds/db-credentials \
  --description "RDS PostgreSQL credentials for WebsiteTester app" \
  --secret-string '{"username":"dbadmin","password":"YourSecurePassword123"}'
```

**Note:** Use the same password you provided in Step 3.

### 5. Deploy EC2 Instance (for database management)
```bash
aws cloudformation create-stack \
  --stack-name devops-infra-instance \
  --template-body file://cfn-infrastructure/infrastructure-ec2-instance.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```
**Important:** This EC2 instance is deployed in the same private subnet as the RDS instance and is required to run the database schema migration script. RDS is not publicly accessible, so this instance acts as a jump host for database management tasks.

### 6. Connect to EC2 Instance via SSM
```bash
# Get the SSM connection command from stack outputs
aws cloudformation describe-stacks \
  --stack-name devops-infra-instance \
  --query "Stacks[0].Outputs[?OutputKey=='SSMConnectionCommand'].OutputValue" \
  --output text

# Or connect directly with instance ID
aws ssm start-session --target <instance-id> --profile <your-profile> --region us-east-1
```

### 7. Run Database Schema Migration
```bash
# Migration script path (inside app image): /websitetester_app/scripts/migrate.py
# Why this path: it keeps schema logic versioned with application code and available
# in every deployed ECS container for repeatable CI/CD and ECS Exec runs.

# Run migration from a running task/container session
python /websitetester_app/scripts/migrate.py
```

### 8. Teardown (to avoid costs)
Delete in reverse order to avoid dependency errors:
```bash
aws cloudformation delete-stack --stack-name devops-infra-instance
aws cloudformation delete-stack --stack-name devops-rds
aws cloudformation delete-stack --stack-name devops-vpc-stack
aws cloudformation delete-stack --stack-name btstrp-db-postgres-iam-stack
```

**Note:** RDS creates a final snapshot on deletion (DeletionPolicy: Snapshot). Delete the snapshot manually in the console if no longer needed.

---

## Accessing RDS from EC2 Instance

### Connect to RDS via psql
```bash
# Connect via SSM to EC2 instance first
aws ssm start-session --target <instance-id>

# Inside the instance, connect to RDS
psql -h <rds-endpoint> -p 5432 -U dbadmin -d appdb

# Example:
psql -h devops-rds-postgres.abc123.us-east-1.rds.amazonaws.com -p 5432 -U dbadmin -d appdb
```

### Verify Database Schema
Once connected to psql, run these commands:

```sql
-- List all tables
\dt

-- Describe websites table structure
\d websites

-- Describe test_results table structure
\d test_results

-- List all indexes
\di

-- Verify foreign key relationship
SELECT conname, conrelid::regclass, confrelid::regclass 
FROM pg_constraint 
WHERE contype = 'f';

-- Check row counts
SELECT COUNT(*) FROM websites;
SELECT COUNT(*) FROM test_results;

-- Exit psql
\q
```

---

## Python Connection

The application retrieves credentials automatically from Secrets Manager using boto3.
No hardcoded passwords are used anywhere in the codebase.

```python
# rds_connection.py handles this automatically
# Credentials are pulled from Secrets Manager: rds/db-credentials
# Connection info is pulled from CloudFormation stack outputs: devops-rds
conn = rds_connection.get_connection()
```

**Locally:** boto3 uses your `all-aws-admin` CLI profile automatically.
**In AWS (CodeBuild/ECS/Lambda):** boto3 uses the attached IAM role automatically.

---

## Stack Names

- **VPC Stack**: devops-vpc-stack
- **DB/Postgres IAM Bootstrap Stack**: btstrp-db-postgres-iam-stack
- **RDS Stack**: devops-rds
- **EC2 Instance Stack**: devops-infra-instance

## Template Parameters

### RDS (postgres-rds-cfn.yaml)
- **VpcStackName**: VPC stack name (default: devops-vpc-stack)
- **DBInstanceClass**: Instance type (default: db.t3.micro)
- **DBAllocatedStorage**: Storage in GB (default: 20)
- **DBName**: Database name (default: appdb)
- **DBUsername**: Master username (default: dbadmin)
- **DBPassword**: Master password (required, min 8 chars)
- **MultiAZ**: Enable Multi-AZ (default: false)

### EC2 Instance (infrastructure-ec2-instance.yaml)
- **VpcStackName**: VPC stack name (default: devops-vpc-stack)
- **InstanceType**: Instance type (default: t3.micro)

## Cost Optimization

- Use db.t3.micro for development
- Set MultiAZ to false for non-production
- Delete stacks when not in use
- Snapshots are created on deletion (DeletionPolicy: Snapshot)
