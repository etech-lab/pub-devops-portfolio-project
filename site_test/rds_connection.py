# rds_connection.py
import json
import boto3
import psycopg2
from typing import Dict, Optional


def get_db_credentials(
    secret_name: str = "rds/db-credentials", region: str = "us-east-1"
) -> dict:
    """Retrieve database credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def get_connection_info(
    stack_name: str = "devops-rds", region: str = "us-east-1"
) -> dict:
    """Retrieve RDS connection info from CloudFormation stack outputs."""
    cfn = boto3.client("cloudformation", region_name=region)
    response = cfn.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def get_connection(region: str = "us-east-1"):
    """Return a psycopg2 connection using Secrets Manager credentials and CFN outputs."""
    credentials = get_db_credentials(region=region)
    info = get_connection_info(region=region)
    return psycopg2.connect(
        host=info["DBEndpoint"],
        port=info["DBPort"],
        database=info["DBName"],
        user=credentials["username"],
        password=credentials["password"],
    )


def save_test_result(
    conn,
    url: str,
    reachable: bool,
    headers: Optional[Dict] = None,
):
    """Insert or update website and save test result."""
    headers = headers or {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO websites (url)
            VALUES (%s)
            ON CONFLICT (url) DO UPDATE SET url = EXCLUDED.url
            RETURNING id;
        """,
            (url,),
        )
        website_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO test_results (
                website_id, status_code, date_header, server_header,
                content_type, content_length, last_modified
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """,
            (
                website_id,
                headers.get("Status-Code") if reachable else None,
                headers.get("Date"),
                headers.get("Server"),
                headers.get("Content-Type"),
                headers.get("Content-Length"),
                headers.get("Last-Modified"),
            ),
        )
    conn.commit()
