# oci-usage-to-s3-bucket-csv
Creates a CSV file of monthly usage that is uploaded to an S3 bucket

based on: https://github.com/oracle/oci-python-sdk/tree/master/examples/showusage

# Prerequisites

1. Python3 >= 3.11
2. Local Configuration or Instance Principal Authentication for OCI
3. Local Configuration for AWS/Azure/GCP S3 Endpoints

# Usage

```python ./oci-product-usage-to-csv.py [options]