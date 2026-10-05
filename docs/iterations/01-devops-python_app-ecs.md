# Iteration 1: Website Tester — ECS Architecture & CI/CD Deployment

## Overview

Website Tester is a Python-based application designed to automate the validation of website URLs —
checking availability, response codes, and connectivity. This document covers the first iteration of the project, which is a containerized application deployed to AWS ECS, backed by a PostgreSQL RDS database, and accessed securely over SSH.

The goal of this iteration is to establish a solid cloud infrastructure foundation using
infrastructure-as-code (AWS CloudFormation), containerization (Docker), and a CI/CD pipeline
for automated builds and deployments. Rather than a polished user-facing product, this iteration
is intentionally scoped as an interactive tool. A DevOps engineer SSHs into the running container
to execute tests and review results directly.

### Application Code (Already Implemented)
- The Python website testing workflow is in place and tested.
- Database access is implemented with secure credential retrieval from AWS Secrets Manager and connection details from CloudFormation outputs.
- The codebase has been run and verified as functional in its current pre-ECS CI/CD state.

### Infrastructure Templates (Already Implemented)
- CloudFormation templates for networking, IAM, PostgreSQL RDS, and infrastructure management resources are already authored.
- Stack dependencies and deployment order are defined.
- Supporting operational steps (including schema setup and secure access patterns) are already documented and tested.

### Iteration Focus
This document does not cover initial application coding or infrastructure template creation.
The focus of this iteration is implementing and documenting the containerized ECS + CI/CD delivery path for the existing Website Tester application.

## Part 1: Dockerfile Design and Container Build
Full Dockerfile: [Containers/Docker/Dockerfile](../../Containers/Docker/Dockerfile)

This Dockerfile exists to make runtime behavior consistent and secure for ECS.

### Important components of the Dockerfile and docker-entrypoint bash script

FROM python:3.12-slim

I used a Python base image (python:3.12-slim) instead of starting from a plain Linux image and installing Python manually. This keeps the image smaller, reduces setup complexity, and gives a consistent Python runtime that is easier to maintain across environments.

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_DEFAULT_REGION=us-east-1 SSH_USER=webtester SSH_PUBLIC_KEY_SECRET_NAME=websitetester/ssh/webtester-public-key

Sets predictable Python and AWS/SSH defaults so the container starts with known behavior, including the Secrets Manager name used to fetch the SSH public key at startup.

PYTHONDONTWRITEBYTECODE=1 Prevents Python from writing `.pyc` cache files, keeping the container image clean.
PYTHONUNBUFFERED=1 Forces stdout/stderr output to flush immediately, so logs appear in real time in ECS.

RUN apt-get install -y --no-install-recommends openssh-server ca-certificates curl wget jq awscli

Adds SSH support plus diagnostics and AWS tooling in-container (`curl`, `wget`, `jq`, `awscli`) so engineers can securely access and troubleshoot from the running task when needed.

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

Uses an entrypoint script to fetch the SSH public key from Secrets Manager, configure `authorized_keys`, persist ECS task credential environment variables into `/etc/profile.d/ecs-task-role.sh`, and then run `sshd` in foreground mode (`-D`) so the container process stays alive.

EXPOSE 22

This will allow the container to listen on port 22.

### Step 1

**NOTE** Since the application is designed in this iteration to use an SSH daemon, a secret is required for the SSH public key (`websitetester/ssh/webtester-public-key`). A separate secret is also required for the RDS PostgreSQL credentials (`rds/db-credentials`).

Use the infrastructure EC2 instance to build the Docker image. Deploy `devops-vpc-stack` and `devops-infra-instance`, then connect with SSM and clone the repo. Docker is installed automatically by `UserData` in `infrastructure-ec2-instance.yaml`, so no manual Docker install is needed.

After cloning the repo, run:
> [!IMPORTANT]
> ```bash
> docker build -f Containers/Docker/Dockerfile -t websitetester:dev .
> ```

![docker build](../images/01-devops-python_app-ecs/011-iter_DockerBuildConfirmationImage.png)

### Step 2

The container has been created so next we will perform a smoke test. Start the container with:

```bash
docker run -d --name websitetester-smoke -p 2222:22 websitetester:dev
```

> [!NOTE]
> In the current image, SSH login auto-starts `python -m site_test`. At this stage of testing, the application will fail until the database migration has been completed.

This will start the container in detached mode and map port 2222 on the host to port 22 in the container for SSH access.
![docker run](../images/01-devops-python_app-ecs/012-iter_DockerRun.png)

We can delve a little further by utilizing `docker exec` for executing commands.

```bash
docker exec websitetester-smoke sh -c "/usr/sbin/sshd -t && ps aux | grep [s]shd"
```

This command checks the SSH daemon configuration and verifies that the sshd process is running inside the container.
![docker exec](../images/01-devops-python_app-ecs/013-iter_DockerExec.png)

### Step 3

Container has been created and tested for the ssh daemon configuration. Next we'll create an AWS ECR repo.

```bash
aws ecr create-repository --repository-name websitetester --region us-east-1
```

This command creates a new ECR repository named "websitetester" in the us-east-1 region to store our Docker images.
![ECR Create](../images/01-devops-python_app-ecs/014-iter_CreateECR.png)

With the repository created, the next step is to authenticate Docker to ECR, tag the local image, and push it up. The three commands below handle that in sequence.

The first command retrieves the AWS account ID from the current IAM identity and constructs the full ECR URI, storing both as environment variables so they can be reused in the next commands without hardcoding account-specific values.

The second command authenticates the local Docker client to ECR using a short-lived password generated by the AWS CLI, so subsequent push commands are authorized.

The third command tags the locally built image with the full ECR URI and pushes it to the repository, making it available for ECS to pull during deployments.

> [!IMPORTANT]
> ```bash
> ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
> ECR_URI="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/websitetester"
>
> aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
>
> ```

![ECR Login](../images/01-devops-python_app-ecs/015-iter_DockerCredentials.png)

With Docker authenticated to ECR, the local image is tagged with the full ECR URI and pushed to the repository. The tag command maps the local image name to the ECR destination, and the push command uploads the image layers making it available for ECS to pull during deployments.

> [!IMPORTANT]
> ```bash
> docker tag websitetester:dev "${ECR_URI}:dev"
> docker push "${ECR_URI}:dev"
> ```

![ECR Tag & Push](../images/01-devops-python_app-ecs/016-iter_DockerTag&Push.png)

Let's also confirm the creation of the image in the AWS console.
![console ecr image](../images/01-devops-python_app-ecs/017-iter_ConsoleEcrImage.png)

## Part 2 ECS Deployment and Validation

### Step 1 Deploy rest of infrastructure for ECS testing.

Majority of the infrastructure has been built out and tested for the core functionality of the application. Now we are going to focus on the ECS cluster and the network load balancer. In the base application deployment and testing no NLB was needed, but since the devops architecture will be multi-AZ. I went ahead and made a separate cfn template for the the NLB stack, [cfn-infrastructure/nlb-cfn.yaml](../../cfn-infrastructure/nlb-cfn.yaml) which will be deployed in the part.

### Deploy order for ECS

1. `devops-vpc-stack` using `cfn-infrastructure/vpc-network.yaml`
2. `devops-nlb-stack` using `cfn-infrastructure/nlb-cfn.yaml`
3. `ecs-cluster-stack` using `Containers/ECS/ecs-cluster.yaml`
4. `ecs-service-stack` using `Containers/ECS/ecs-service.yaml`

This order ensures the ECS service can import the existing NLB target group output and register tasks during deployment.

### Core ECS components

- **Task definition** is the runtime blueprint for the container. It defines the image in ECR, CPU/memory, port mappings, logging, and IAM roles used by the task.
- **ECS service** maintains desired task count and replaces unhealthy tasks automatically. It also registers tasks with the NLB target group.
- **ECS cluster** is the logical boundary where services and tasks run. For this iteration, the service uses Fargate launch type.

### How ECS ties into RDS

- The containerized app reads DB credentials from Secrets Manager and RDS connection details from CloudFormation stack outputs.
- Because of that runtime behavior, RDS and required secrets must exist before ECS tasks can start successfully.

### Step 2 Migrate RDS schema and test application

After the ECS service is deployed and the task is reachable through the Network Load Balancer, connect to the running container over SSH. In this iteration, the application auto-starts when the SSH session begins, but the first run will fail until the database schema has been created.

Use the following commands:

> [!IMPORTANT]
> ```bash
> ssh -i ~/.ssh/webtester-key webtester@<your-current-nlb-dns>
> unset AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_CREDENTIALS_FULL_URI
> python /websitetester_app/scripts/migrate.py
> ```

The `unset` command is needed in the current iteration because the SSH shell can inherit some ECS credential-related variables as empty strings. When that happens, `boto3` may try to use an empty file path or endpoint value while resolving task credentials, which prevents the migration script from authenticating to AWS correctly. Removing those empty variables allows the script to use the valid task-role credentials that are still available in the session.

Once the schema migration completes successfully, the application can be run again and should be able to save test results to RDS.

![Script Migration](../images/01-devops-python_app-ecs/0112-iter_ScriptMigrate.png)

Now the script is migrated for the database functionality we can test the application.
![Application Test](../images/01-devops-python_app-ecs/0113-iter_ApplicationTest.png)
Test was successful and now the website tester v1 is fully functional and can be utilized for some devops ci/cd architecture.

### Part 3: AWS Developer Tools Infrastructure Pipeline

This iteration uses AWS CodePipeline and AWS CodeBuild to automate infrastructure deployments.

## Step 1: Set up CodeBuild role

For bootstrap setup, deploy these one-time IAM foundational templates:

- `cfn-infrastructure/btstrp-db-postgres-iam-roles.yaml`
- `cfn-infrastructure/btstrp-codebuild-role-s3artifbkt.yaml`

These `btstrp-*` templates are deployed once in the AWS console before the CodePipeline begins managing regular infrastructure stacks.

This stack is more for future use and general use for deploying RDS `btstrp-db-postgres-iam-roles.yaml`. It will still fit into overall architecture.
 
Deploy `btstrp-codebuild-role-s3artifbkt.yaml` to create the IAM roles and permissions used by CodeBuild and CloudFormation. It also creates an s3 artifact bucket for codepipeline. One thing to note about the s3 artifact bucket is that versioning is required for codepipeline.

This stack creates:
- `codebuild-infra-deploy-role`: IAM role that CodeBuild assumes.
- `codebuild-infra-deploy-policy`: Managed policy with CloudFormation, EC2, RDS, IAM, and S3 permissions.
- `cloudformation-infra-deploy-role`: IAM execution role that CloudFormation assumes during deploy actions.
- `cloudformation-infra-deploy-policy`: Managed policy attached to the CloudFormation execution role.
- `CloudFormationDeployRoleArn`: Output consumed by the infrastructure pipeline stack.

## Step 2: Create GitHub CodeStar connection

In the AWS Console, navigate to CodePipeline > Settings > Connections > Create connection. Select Github as the provider and enter the connection name github-websitetester.

Choose Install a new app  and select the correct GitHub owner/org. You will then be directed to a github page for authorization and to select the a repos or all repos that this app has access to. The application can be viewed under integrations on the settings page of github.
![Code Connections](../images/01-devops-python_app-ecs/0121-iter_GitHubApp.png)

When that authorization completes successfully, the connection status should show Available in AWS.
![Code Connection Status](../images/01-devops-python_app-ecs/0122-iter_AwsCodeConnectionStatus.png)

Save the connection ARN; it is required for the CodePipeline stack parameter.

## Step 3: Set up CodePipeline and CodeBuild

Deploy `btstrp-codepipeline.yaml` using the stack name `btstrp-codepipeline-infra-stack`.

Required parameters:
- `GitHubOwner`: GitHub organization or username
- `GitHubRepo`: Repository name
- `GitHubBranch`: Branch to track (default: main)
- `GitHubConnectionArn`: ARN from Step 2
- `CodeBuildRoleArn`: ARN output from Step 1
- `ArtifactBucketName`: S3 bucket created by btstrp-codebuild-infra-role-stack for pipeline artifacts
- `ApprovalEmail`: Email to receive manual approval notifications
- `CloudFormationDeployRoleArn`: ARN output from Step 1 for CloudFormation deploy actions

> [!NOTE]
> AWS will send a subscription confirmation email to the address provided. Confirm it or approval notifications will not send.

### Notable components of codepipeline cfn template

CodePipeline has its own individual role to assume and permissions policy to allow for the deployment of the website tester infrastructure deployment. Also included an SNS topic and Subscription for the approval stage of the pipeline.

This stack creates:
- CodeBuild validation project (`infra-validate`)
- CodePipeline with stages: Source (GitHub) → Validate (CodeBuild) → Approval (Manual) → Deploy (CloudFormation)

The deploy stage applies infrastructure templates in this order:
- RunOrder 1 (parallel): `devops-vpc-stack` from `cfn-infrastructure/vpc-network.yaml`, and `devops-secrets-stack` from `cfn-infrastructure/pl-secrets.yaml`
- RunOrder 2: `devops-nlb-stack` from `cfn-infrastructure/nlb-cfn.yaml`

The infrastructure EC2 instance stack (`cfn-infrastructure/infrastructure-ec2-instance.yaml`) is now deployed manually as needed for ad-hoc testing and setup.

`pl-secrets.yaml` is pipeline-only and fully automated. It creates:
- `rds/db-credentials-pl` with autogenerated password
- `websitetester/ssh/webtester-public-key-pl` for ECS SSH key retrieval

The manual path remains `cfn-infrastructure/secrets.yaml` for non-pipeline setup.

The pipeline automatically triggers on pushes to the `main` branch and runs `cfn-lint` validation on all templates.

The codebuild project infra-validate uses BUILD_GENERAL1_SMALL for `ComputeType`, which uses the latest Linux container image available. A larger compute type could be used if needed, but since its a simple project small should suffice. Also, set the parameter `TimeoutInMinutes` to 15 minutes vs the default 60 minutes.

The `InfraPipeline` Approval pipeline configuration parameter uses key value pairs from the CodePipeline manual approval action type:
- `NotificationArn`: SNS topic ARN used to send the approval notification email.
- `ExternalEntityLink`: URL shown to the approver for quick review context (here it points to the exact GitHub commit).
- `CustomData`: short approval instructions/checklist shown in the approval message and console.

These values listed above are passed in `Configuration` for the Manual approval action and are evaluated by CodePipeline when the Approval stage is reached.

The `InfraPipeline` is intended to deploy those resources needed for the application to run on. The `Deploy` stage will deploy a VPC, NLB and the secrets needed for things such as our postgres SQL database and public SSH keys needed for our first iteration, which doesn't currently have a frontend for a GUI.

### Notable components of infra-buildspec yaml file

The buildspec file is a part of codebuild and its pretty much for running linux bash and shell commands in a AWS container for compute. It has AWS CLI baked in along with the docker daemon and codebuild environment variables. The pre build phase install pip packages from the requirements.txt file. The build phase runs `cfn-lint --non-zero-exit-code error` on all of the templates under cfn-infrastructure in the project repo.

## Step 4: Deploy the Infra code pipeline

In the previous step a SNS Topic was created for the approval stage lets confirm the it was subscribed to in the console ![SNS Topic Subscription](../images/01-devops-python_app-ecs/0117-iter_SubscribeSnsTopic.png).

Now we can run and test the `btstrp-codepipeline.yaml`. The pipeline ran when we deployed the stack. Ran into a couple issues with the linter for the validate stage. The pipeline won't complete without a accepting a manual approval at the approval stage. Clicking on the link will direct you to a github webpage with the last changes made to a repo via a git push.
![Review Changes](../images/01-devops-python_app-ecs/0119-iter_ReviewChanges.png)
Navigate back to the pipeline tab in the browser and you should see a box that popped up for approval.
![Manual Approval](../images/01-devops-python_app-ecs/0118-iter_ManualApprove.png)

Image from notification email.
![Approval Email](../images/01-devops-python_app-ecs/0120-iter_ApprovalEmail.png)

The pipeline completed successfully.
![Pipeline Completed](../images/01-devops-python_app-ecs/0123-iter_InfraPipelineCompleted.png)

## Part 4: Deploy Application Pipeline

Deploy the cfn template `btstrp-codepipeline-app.yaml`. Once the the cfn template is deployed the pipeline will run for the first time. You'll also receive a confirmation email to subscribe to the sns topic created via the stack for validation. Once the pipeline reaches the approval stage we need to submit the manual approval just like in the infra pipeline. ![App Manual Approval Stage](../images/01-devops-python_app-ecs/0124-iter_ApplicationPipelineApproval.png) 
![App Pipeline Approval Box](../images/01-devops-python_app-ecs/0125-iter_AppPipelineManualApproval.png)


### Notable components of app codepipeline cfn template

The app pipeline has a lot of similar parameters to the infra one with the exception.
- `EcrRepositoryName`: Name of you ECR repository.
- `EcsServiceStackName`: Name of your ECS service cfn stack.
- `NlbStackName`: Name of the nlb stack deployed by infra pipeline.

The app pipeline uses four separate buildspec files — `app-validate-buildspec.yml`, `app-build-push-buildspec.yml`, `app-migrate-buildspec.yml` and `app-verify-buildspec.yml` — each mapped to its own CodeBuild project and pipeline stage. This separation keeps each stage focused on a single responsibility rather than bundling all logic into one file.

`app-validate-buildspec.yml` runs `cfn-lint` against the templates and any other static checks before anything is built or deployed. Keeping validation isolated means a linting failure stops the pipeline early without consuming the larger compute resources needed for a Docker build.

`app-migrate-buildspec.yml` for the migration task a one time ECS task is spun up in the VPC of the application to migrate the database schema for the postgres sql database. This was done as a work around since the app code pipeline instance of the codebuild image is ran outside of the application VPC.

`app-build-push-buildspec.yml` handles the Docker image build and ECR push. This stage uses a medium compute type with privileged mode enabled, which is required for Docker-in-Docker builds. Separating this from validation means the heavier build environment is only used when the code has already passed static checks.

`app-verify-buildspec.yml` runs after the deploy stage and confirms the ECS service stabilized and the NLB endpoint is reachable. Keeping post-deploy verification in its own buildspec makes it easy to update or extend verification logic independently without touching the build or validation steps.

This structure also makes pipeline failures easier to diagnose. When a run fails, the stage name immediately points to whether the issue was a template problem, a build problem, or a post-deploy problem.

### Notable components of buildspecs/app-* files

No need to go into great detail since this is essentially to automate what We have already done for building docker images and containers. The `app-build-push-buildspec.yml` handles building and tagging the docker image and pushing it to an ECR. The buildspec file `app-validate-buildspec.yml` uses a module from the application to run a basic test to verify the application is working as intended.

### Notable components of ECS directory files
The directory for containers, which in this iteration is for ECS. The `ecs-cluster.yaml` cfn template file and the only property used for creating the cluster is the cluster settings for containers insight. This just provides enhanced observability for ECS metrics.

When looking at the documentation for the cloud formation templates related to ECS services there are a ton of properties to take into consideration. For this project I tried to make production minded choices, but ultimately its still just a project and things are likely to change in future iterations. The `ecs-service.yaml` has several ECS:: templates in it. The first thing we can point out is AWS::ECS::TaskDefinition, which there are two of them one for the application and the other for the task of migrating the database schema script for an ECS task. The application task definition `RequiresCompatibilities` property accepts a value for ECS launch types, this property isn't required is more of a validation guard, if we decide to use multiple launch types in the cluster. For this first iteration we went with Fargate. Under that is `NetworkMode` and its value is `awsvpc`, which is the required value for for Fargate. For the migrate task definition the `EntryPoint` property is used to override the `docker-entrypoint.sh` that is ran when the container starts up. The value is python which is a value passed to the docker image, since the image is a python image, we could use a different value based on the language which an executable would be available for the desired language. The `command` property maps to the Cmd inside the docker container. This allows us to run the migrate script in a separate task definition different from the application one.

Next component to broach is the ECS service. The `DependsOn` property is a universal resource attribute that depends on the completion of the application task definition to complete before the ECS service part of the cfn template is deployed. 

## Part 5: Confirmation of the application deployment

The application pipeline was successfully deployed now we need to confirm that the application works just like we did during the manual deployment of the web site tester application. For this first iteration, the plan was to SSH into the running ECS task, where the shell was set to auto launch the application. The private key is already on my machine and the public key was stored in secrets manager. We can get the NLB DNS from the NLB stack outputs and using the following command. 
```bash
ssh -i ~/.ssh/webtester-key webtester@<nlb-dns>
```
![SSH to App Website Tester Instance](../images/01-devops-python_app-ecs/0126-iter_SshWbtstAppPy.png)

Once you input the ssh command to connect to the container. The application interface will already be launched. From this point you just need to enter a single url or urls separated by a space. We can also enter a list of urls delimited by a new line or comma, the functionality of the application is unimportant since this is a project to showcase DevOps skills and it will be altered in later iterations. The results from the test can be seen in the image below.
![Website Tester Results](../images/01-devops-python_app-ecs/0127-iter_WbtstResults.png)

The following images are documented for completion. I've included images from both the infra and app pipelines. 
![Infra Pipeline Completed](../images/01-devops-python_app-ecs/0128-iter_InfraPipeline.png)
![App Pipeline Completed](../images/01-devops-python_app-ecs/0129-iter_AppPipeline.png)
Next is an image of the ECS cluster from the AWS console. 
![ECS Cluster](../images/01-devops-python_app-ecs/0130-iter_EcsCluster.png)
Lastly, is an image of the RDS database from the AWS console.
![RDS Database](../images/01-devops-python_app-ecs/0131-iter_RdsDatabase.png)



