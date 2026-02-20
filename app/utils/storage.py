from minio import Minio
from minio.error import S3Error
from datetime import datetime
import json
import os
import io
import logging

logger = logging.getLogger(__name__)

def get_minio_client():
    """Get MinIO client instance"""
    return Minio(
        os.getenv('MINIO_ENDPOINT', 'minio:9000'),
        access_key=os.getenv('MINIO_ROOT_USER', os.getenv('MINIO_USER', 'minioadmin')),
        secret_key=os.getenv('MINIO_ROOT_PASSWORD', os.getenv('MINIO_PASSWORD', 'minioadmin123')),
        secure=False  # Set to True if using HTTPS
    )

def ensure_bucket_exists(client, bucket_name):
    """Ensure bucket exists, create if not"""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
    except S3Error as e:
        logger.error(f"Error ensuring bucket exists: {e}", exc_info=True)
        raise

def store_raw_output(tenant_id: int, tool: str, data: any):
    """
    Store raw tool output in MinIO

    Args:
        tenant_id: Tenant ID
        tool: Tool name (subfinder, dnsx, httpx, etc.)
        data: Data to store (will be JSON serialized)
    """
    try:
        client = get_minio_client()
        bucket_name = f'tenant-{tenant_id}'

        # Ensure bucket exists
        ensure_bucket_exists(client, bucket_name)

        # Generate object name with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        object_name = f'{tool}/{timestamp}.json'

        # Convert data to JSON bytes
        if isinstance(data, (list, dict)):
            json_str = json.dumps(data, indent=2, default=str)
        else:
            json_str = json.dumps({'data': data}, default=str)

        data_bytes = json_str.encode('utf-8')

        # Upload to MinIO
        client.put_object(
            bucket_name,
            object_name,
            data=io.BytesIO(data_bytes),
            length=len(data_bytes),
            content_type='application/json'
        )
        logger.info(f"Stored {tool} output to {bucket_name}/{object_name}")
        return object_name
    except (S3Error, Exception) as e:
        # Log but don't fail - MinIO is optional
        logger.warning(f"MinIO storage failed (non-critical): {e}")
        return None

def retrieve_raw_output(tenant_id: int, object_name: str):
    """
    Retrieve raw tool output from MinIO

    Args:
        tenant_id: Tenant ID
        object_name: Object name in MinIO

    Returns:
        Parsed JSON data
    """
    client = get_minio_client()
    bucket_name = f'tenant-{tenant_id}'

    try:
        response = client.get_object(bucket_name, object_name)
        data = response.read()
        return json.loads(data.decode('utf-8'))
    except S3Error as e:
        logger.error(f"Error retrieving output: {e}", exc_info=True)
        raise
    finally:
        if response:
            response.close()
            response.release_conn()

def list_tool_outputs(tenant_id: int, tool: str, limit: int = 10):
    """
    List recent outputs for a specific tool

    Args:
        tenant_id: Tenant ID
        tool: Tool name
        limit: Maximum number of items to return

    Returns:
        List of object names
    """
    client = get_minio_client()
    bucket_name = f'tenant-{tenant_id}'

    try:
        objects = client.list_objects(bucket_name, prefix=f'{tool}/', recursive=True)
        results = []

        for obj in objects:
            results.append({
                'name': obj.object_name,
                'size': obj.size,
                'last_modified': obj.last_modified
            })

            if len(results) >= limit:
                break

        # Sort by last modified descending
        results.sort(key=lambda x: x['last_modified'], reverse=True)

        return results
    except S3Error as e:
        logger.error(f"Error listing outputs: {e}", exc_info=True)
        return []
