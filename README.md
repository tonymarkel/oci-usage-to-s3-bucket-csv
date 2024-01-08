# oci-usage-to-s3-bucket-csv
Creates a CSV file of monthly usage that is uploaded to an S3 bucket

based on: https://github.com/oracle/oci-python-sdk/tree/master/examples/showusage

# Prerequisites

1. Python3 >= 3.11
2. Local Configuration or Instance Principal Authentication for OCI
3. Local Configuration for AWS/Azure/GCP S3 Endpoints

# Usage

```
python ./oci-product-usage-to-csv.py [options]
```
# Application Command line options

```
  -c config    - OCI CLI Config File
  -t profile   - profile inside the config file
  -p proxy     - Set Proxy (i.e. www-proxy-server.com:80)
  -ip          - Use Instance Principals for Authentication
  -dt          - Use Instance Principals with delegation token for cloud shell
  -cd          - Compartment Depth (defaults to 3)
  -ds date     - Start Date in YYYY-MM-DD format (defaults to the first day of last month)
  -de date     - End Date in YYYY-MM-DD format (defaults to the last day of last month)
  -ld days     - Add Days Combined with Start Date (de is ignored if specified)
```

# Info:
   List Tenancy Usage Including Product, Region, and Compartment

# Connectivity:
   Option 1 - User Authentication
      $HOME/.oci/config, please follow - https://docs.cloud.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm
      OCI user part of ShowUsageGroup group with below Policy rules:
         Allow group ShowUsageGroup to inspect tenancies in tenancy
         Allow group ShowUsageGroup to read usage-report in tenancy
      (optional for AWS Native S3)
      $HOME/.aws/config
      $HOME/.aws/credentials

   Option 2 - Instance Principle
      Compute instance part of DynShowUsageGroup dynamic group with policy rules:
         Allow dynamic group DynShowUsageGroup to inspect tenancies in tenancy
         Allow dynamic group DynShowUsageGroup to read usage-report in tenancy

# Modules Included:
- oci.identity.IdentityClient
- oci.usage_api.UsageapiClient

APIs Used:
- IdentityClient.get_tenancy               - Policy TENANCY_INSPECT
- IdentityClient.list_region_subscriptions - Policy TENANCY_INSPECT
- UsageapiClient.request_summarized_usages - read usage-report