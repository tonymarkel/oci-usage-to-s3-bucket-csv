# coding: utf-8
# Copyright (c) 2016, 2023, Oracle and/or its affiliates.  All rights reserved.
# This software is dual-licensed to you under the Universal Permissive License (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl or Apache License 2.0 as shown at http://www.apache.org/licenses/LICENSE-2.0. You may choose either license.

##########################################################################
# oci-product-usage-to-csv.py
#
# @authors: 
# Adi Zohar, Oct 07 2021
#  - OCI Authentication
#
# Tony Markel, Dec 08 2023
#  - CSV Generation
#
# Supports Python 3
##########################################################################

import sys
import argparse
import datetime
import oci
import os
import platform
import boto3
import awscli
from time import mktime
from datetime import datetime
from datetime import date
from datetime import timedelta

##########################################################################
# custom argparse *date* type for user dates
##########################################################################
def valid_date_type(arg_date_str):
    try:
        return datetime.strptime(arg_date_str, "%Y-%m-%d")
    except ValueError:
        msg = "Given Date ({0}) not valid! Expected format, YYYY-MM-DD!".format(arg_date_str)
        raise argparse.ArgumentTypeError(msg)


##########################################################################
# check service error to warn instead of error
##########################################################################
def check_service_error(code):
    return ('max retries exceeded' in str(code).lower() or
            'auth' in str(code).lower() or
            'notfound' in str(code).lower() or
            code == 'Forbidden' or
            code == 'TooManyRequests' or
            code == 'IncorrectState' or
            code == 'LimitExceeded'
            )

##########################################################################
# Create signer for Authentication
# Input - config_profile and is_instance_principals and is_delegation_token
# Output - config and signer objects
##########################################################################
def create_signer(config_file, config_profile, is_instance_principals, is_delegation_token):

    # if instance principals authentications
    if is_instance_principals:
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            config = {'region': signer.region, 'tenancy': signer.tenancy_id}
            return config, signer

        except Exception:
            print("Error obtaining instance principals certificate, aborting", 0)
            raise SystemExit

    # -----------------------------
    # Delegation Token
    # -----------------------------
    elif is_delegation_token:

        try:
            # check if env variables OCI_CONFIG_FILE, OCI_CONFIG_PROFILE exist and use them
            env_config_file = os.environ.get('OCI_CONFIG_FILE')
            env_config_section = os.environ.get('OCI_CONFIG_PROFILE')

            # check if file exist
            if env_config_file is None or env_config_section is None:
                print("*** OCI_CONFIG_FILE and OCI_CONFIG_PROFILE env variables not found, abort. ***")
                print("")
                raise SystemExit

            config = oci.config.from_file(env_config_file, env_config_section)
            delegation_token_location = config["delegation_token_file"]

            with open(delegation_token_location, 'r') as delegation_token_file:
                delegation_token = delegation_token_file.read().strip()
                # get signer from delegation token
                signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(delegation_token=delegation_token)

                return config, signer

        except KeyError:
            print("* Key Error obtaining delegation_token_file")
            raise SystemExit

        except Exception:
            raise

    # -----------------------------
    # config file authentication
    # -----------------------------
    else:
        config = oci.config.from_file(
            (config_file if config_file else oci.config.DEFAULT_LOCATION),
            (config_profile if config_profile else oci.config.DEFAULT_PROFILE)
        )
        signer = oci.signer.Signer(
            tenancy=config["tenancy"],
            user=config["user"],
            fingerprint=config["fingerprint"],
            private_key_file_location=config.get("key_file"),
            pass_phrase=oci.config.get_config_value_or_default(config, "pass_phrase"),
            private_key_content=config.get("key_content")
        )
        return config, signer

# FUNCTION: Daily Usage by Product and Compartment
def usage_daily_product(usageClient, tenant_id, time_usage_started, time_usage_ended, tier, csv_filename):

    try:
        # oci.usage_api.models.RequestSummarizedUsagesDetails
        requestSummarizedUsagesDetails = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id            = tenant_id,
            granularity          = 'DAILY',
            query_type           = 'COST',
            compartment_depth    = tier,
            group_by             = ['region', 'skuPartNumber', 'skuName', 'compartmentPath'],
            time_usage_started   = time_usage_started.strftime('%Y-%m-%dT%H:%M:%SZ'),
            time_usage_ended     = time_usage_ended.strftime('%Y-%m-%dT%H:%M:%SZ'),
            is_aggregate_by_time = True
        )

        # usageClient.request_summarized_usages
        request_summarized_usages = usageClient.request_summarized_usages(
            requestSummarizedUsagesDetails,
            retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
        )
        # Header
        csv_header = "\"Vendor\",\"Region\",\"Tier\",\"Product\",\"Day\",\"Cost\"\n"
        # print(csv_header)
        f = open(csv_filename, "w")
        f.writelines(csv_header)
        f.close()

        # Rows
        f = open(csv_filename, "a")
        for item in request_summarized_usages.data.items:
            # only operate on rows with a cost identified to avoid "NoneType" errors
            if item.computed_amount:
                # of those items only select rows where the rounded amount is over a penny
                if item.computed_amount < 0.005:
                    continue
                row = "\"Oracle\",\"" + item.region + "\",\"" + item.compartment_path + "\",\"" + item.sku_part_number + " " + item.sku_name + "\",\"" + str(round(item.computed_amount, 2)) + "\"\n"
                f.writelines(row)
                # print(row)
            else:
                continue

        
        f.close()

    except oci.exceptions.ServiceError as e:
        logging.getLogger().debug("\nService Error at 'usage_daily_product' - " + str(e))

    except Exception as e:
        logging.getLogger().debug("\nException Error at 'usage_daily_product' - " + str(e))

def upload_to_bucket(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False

    Uncomment the below when using a S3 compatible endpoint on a non-AWS provider. 
    Use environment variables or credential management systems to store and retrieve credentials.

    s3 = boto3.resource(
        's3',
        region_name="ap-sydney-1",
        aws_secret_access_key=os.environ.get('S3_SECRET_ACCESS_KEY'),
        aws_access_key_id=os.environ.get('S3_ACCESS_KEY'),
        endpoint_url="https://ocicpm.compat.objectstorage.ap-sydney-1.oraclecloud.com"
    )
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def main():

    # Create Default String for last month's usage data
    this_first = date.today().replace(day=1)
    prev_last = this_first - timedelta(days=1)
    prev_first = prev_last.replace(day=1)
    first_day = str(prev_first)
    last_day = str(prev_last)

    bucket = "usage-from-oci"

    # Get Command Line Parser
    # parser = argparse.ArgumentParser()
    parser = argparse.ArgumentParser(usage=argparse.SUPPRESS, formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=80, width=130))
    parser.add_argument('-c', default="", dest='config_file', help='OCI CLI Config file')
    parser.add_argument('-t', default="", dest='config_profile', help='Config Profile inside the config file')
    parser.add_argument('-p', default="", dest='proxy', help='Set Proxy (i.e. www-proxy-server.com:80) ')
    parser.add_argument('-ip', action='store_true', default=False, dest='is_instance_principals', help='Use Instance Principals for Authentication')
    parser.add_argument('-dt', action='store_true', default=False, dest='is_delegation_token', help='Use Delegation Token for Authentication')
    parser.add_argument('-cd', default=3, dest='tier', help="Maximum Compartment Depth", type=float)
    parser.add_argument("-ds", default=first_day, dest='date_start', help="Start Date - format YYYY-MM-DD", type=valid_date_type)
    parser.add_argument("-de", default=last_day, dest='date_end', help="End Date - format YYYY-MM-DD, (Not Inclusive)", type=valid_date_type)
    parser.add_argument("-days", default=None, dest='days', help="Add Days Combined with Start Date (de is ignored if specified)", type=int)
    parser.add_argument("-report", default="PRODUCT", dest='report', help="Report Type = PRODUCT / DAILY / REGION / ALL ( Default = ALL )")
    cmd = parser.parse_args()
    tier = cmd.tier

    # Date Validation
    time_usage_started = None
    time_usage_ended = None
    report_type = cmd.report

    if cmd.date_start and cmd.date_start > datetime.now():
        print("\n!!! Error, Start date cannot be in the future !!!")
        sys.exit()

    if cmd.date_start and cmd.date_end and cmd.date_start > cmd.date_end:
        print("\n!!! Error, Start date cannot be greater than End date !!!")
        sys.exit()

    if cmd.date_start:
        time_usage_started = cmd.date_start

    if cmd.days:
        time_usage_ended = time_usage_started + datetime.timedelta(days=cmd.days)
    elif cmd.date_end:
        time_usage_ended = cmd.date_end
    else:
        time_usage_ended = time_usage_started + datetime.timedelta(days=1)

    # Days check
    days = (time_usage_ended - time_usage_started).days

    if days > 93:
        print("\n!!! Error, Max 93 days period allowed, input is " + str(days) + " days, !!!")
        sys.exit()

    config, signer = create_signer(cmd.config_file, cmd.config_profile, cmd.is_instance_principals, cmd.is_delegation_token)
    tenant_id = ""

    try:
        identity = oci.identity.IdentityClient(config, signer=signer)
        if cmd.proxy:
            identity.base_client.session.proxies = {'https': cmd.proxy}

        tenancy = identity.get_tenancy(config["tenancy"]).data
        regions = identity.list_region_subscriptions(tenancy.id).data
        tenant_id = tenancy.id

        # Set home region for connection
        for reg in regions:
            if reg.is_home_region:
                tenancy_home_region = str(reg.region_name)

        config['region'] = tenancy_home_region
        signer.region = tenancy_home_region

    except Exception as e:
        raise RuntimeError("\nError fetching tenant information - " + str(e))

    try:
        usage_client = oci.usage_api.UsageapiClient(config, signer=signer)
        if cmd.proxy:
            usage_client.base_client.session.proxies = {'https': cmd.proxy}
        file_name = "oci_usage_from_" + str(time_usage_started)[:10] + "_to_" + str(time_usage_ended)[:10] + ".csv"
        usage_daily_product(usage_client, tenant_id, time_usage_started, time_usage_ended, tier, file_name)
        upload_to_bucket(file_name, bucket)

    except Exception as e:
        raise RuntimeError("\nError at main function - " + str(e))


##########################################################################
# Main Process
##########################################################################
main()
