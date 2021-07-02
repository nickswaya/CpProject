import json
import pandas as pd
import numpy as np
import requests
from UnitTest import get_selenium_dict
import os
from dotenv import find_dotenv, load_dotenv
from retrying import retry
import logging

class Testing_LIR:

    def __init__(self, hostname, size = ''):
        """ Creates a dictionary of specified size containing all invoices in the line item resolution queue, as well as their invoice ID's needed to dig further into the API

        Args:
            hostname (str): used to easily switch between TEST and PROD environments. Main() passes '.test' by default, but could change once moved to production
            size (str, optional): Number of invoices to instantiate and add to resulting dictionary. Mainly used for testing. Defaults to ''.
        """
        self.hostname = hostname
        self.auth_token, self.refresh_token = Testing_LIR.get_auth_token(self.hostname)
        self.payload = {}
        self.headers = {'accept': 'application/json','Authorization': f'Bearer {self.auth_token}'}
        lir_url = f'https://{self.hostname}apiclient.com/CHPAPO/v2/lineitemresolution?size={size}'
        response = requests.request("GET", lir_url, headers=self.headers)
        self.invoices_dict= json.loads(response.text)['_embedded']['lineitemresolution']
        self.number_invoices = len(self.invoices_dict)

    def get_auth_token(hostname):
        """ Get authorization tokens

        Args:
            hostname (str): Passed by main(). Used to switch between TEST and PROD environments.

        Returns:
            Tuple: (General access token, refresh token)
        """
        client_secret = os.getenv("CLIENT_SECRET")
        token_url = f"https://{hostname}apiclient.com/auth/realms/rest-api/protocol/openid-connect/token"
        payload = f'grant_type=client_credentials&client_id=CHPREST&client_secret={client_secret}'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.request("POST", token_url, headers=headers, data=payload)
        return json.loads(response.text)['access_token'],  json.loads(response.text)['refresh_token']

class Invoice:

    def __init__(self, queue_position, lir_queue):
        """ Creates an invoice object which includes the document ID used to dig further into the API.
            The goal of the Invoice class is to set up a SKU information table, grab needed data, and organize it into a DataFrame

        Args:
            queue_position (int): represents the position of the invoice in the line item resolution dictionary
            lir_queue : accessing the lir_queue dictionary attributes
        """
        self.lir_queue = lir_queue
        self.queue_position = queue_position
        self.document_number = int()
        self.document_amount = float()
        self.approved_amount = float()
        self.freight_amount = float()
        self.document_date = str()
        self.sku_ids = []
        self.document_id = lir_queue.invoices_dict[self.queue_position]['id']

    def get_job_info(self, lir_queue):
        """ Get general invoice information. Primarily grabbing document number.

        Args:
            lir_queue : accessing the lir_queue dictionary attributes
        """
        job_url = lir_queue.invoices_dict[self.queue_position]['_links']['job']['href']
        r = requests.request("GET", job_url, headers=lir_queue.headers, data={})
        job = json.loads(r.text)
        self.document_number = job['documentNumber']
        self.document_amount = job['documentAmount']
        self.approved_amount = job['approvedAmount']
        self.freight_amount = job['freightAmount']
        self.document_date = job['documentDate']


    def sku_matrix_to_df(skus_info, feature_list):
        """ Converts SKU information matrix generated from get_api_sku_info() into a useable DataFrame

        Args:
            skus_info (array): Array generated from get_api_sku_info() containing CenterViews entered information
            feature_list (list): feature list to include in resulting DataFrame

        Returns:
            DataFrame: Pandas DataFrame. Transposed so that each row is a SKU and each column a feature.
        """
        lst = []
        for feature in feature_list:
            a = [sku[feature] for sku in skus_info]
            lst.append(a)
        lst_t = np.transpose(lst)
        return pd.DataFrame(data = lst_t, columns = feature_list)

    @retry(wait_fixed=2000, stop_max_attempt_number=3)
    def get_api_sku_info(self, lir_queue):
        """ Get information entered by CenterViews for each SKU as well as links to PO/Receiving data needed for calculations.
        Adds information to an invoices SKU table

        Args:
            lir_queue : accessing the lir_queue attributes
        """
        logger = logging.getLogger(__name__)
        api_sku_infos_url = f'https://{lir_queue.hostname}apiclient.com/CHPAPO/v2/jobs/{self.document_id}/documentdetails'
        try:
            sku_infos_request = requests.request("GET", api_sku_infos_url, headers=lir_queue.headers, data={})
        except:
            logger.error('failed to get API SKU Info After Retrying')
        skus_info = json.loads(sku_infos_request.text)['_embedded']['documentdetails']
        self.number_skus = len(skus_info)
        self.sku_table = Invoice.sku_matrix_to_df(skus_info, ['documentDetailId', 'quantity', 'unitPrice', 'adjustedQuantity', 'adjustedUnitPrice'])
        self.sku_table['documentDetailId'] = self.sku_table['documentDetailId'].astype('int32')


    def get_po_details(self, lir_queue):
        """ Get purchase order information and arrange into a DataFrame to join to an invoice's SKU table

        Args:
            lir_queue : accessing the lir_queue attributes
        """
        po_df = pd.DataFrame(columns = ['po_detail_id', 'sku_number', 'sku_description', 'po_price'])
        for sku_id in self.sku_table.documentDetailId:
            sku_po_url = f'https://{lir_queue.hostname}apiclient.com/CHPAPO/v2/documentdetails/{int(sku_id)}/podetail'
            po_sku_request = requests.request("GET", sku_po_url, headers=lir_queue.headers, data={})
            po_sku_response = json.loads(po_sku_request.text)
            po_detail_id, sku_number, sku_description, po_price = po_sku_response['poDetailId'], po_sku_response['itemNumber'], po_sku_response['itemDescription'], po_sku_response['unitPrice']
            d = {}
            d['po_detail_id'] = po_detail_id
            d['sku_number'] = sku_number
            d['sku_description'] = sku_description
            d['po_price'] = po_price
            po_df = po_df.append(d, ignore_index=True)
        self.sku_table = self.sku_table.join(po_df)


    def get_receiving_details(self, lir_queue):
        """ Get receiving details needed for calculations. Joins resulting dataframe to an invoice's SKU table

        Args:
            lir_queue : accessing the lir_queue attributes
        """
        rec_df = pd.DataFrame(columns = ['detail_id', 'rec_qty'])
        for sku_id in self.sku_table.documentDetailId:
            sku_receiving_url = f'https://{lir_queue.hostname}apiclient.com/CHPAPO/v2/documentdetails/{int(sku_id)}/receivingdetail'
            sku_rec_request = requests.request("GET", sku_receiving_url, headers=lir_queue.headers, data={})
            sku_rec_response = json.loads(sku_rec_request.text)
            detail_id, rec_qty = sku_rec_response['receivingDetailId'], sku_rec_response['receivingQuantity']
            d = {}
            d['po_detail_id'] = detail_id
            d['rec_qty'] = rec_qty
            rec_df = rec_df.append(d, ignore_index=True)
        self.sku_table = self.sku_table.join(rec_df, rsuffix='r', lsuffix='l')


    def calculate_cost(self):
        """ Adding columns of calculated values to an invoice's SKU table which will be patched
        """
        self.sku_table['adjustedQuantity'] = self.sku_table['rec_qty']
        self.sku_table['extended_sku_cost'] = self.sku_table['quantity'] * self.sku_table['unitPrice']
        self.sku_table['adjustedUnitPrice'] = self.sku_table['extended_sku_cost'] / self.sku_table['adjustedQuantity']
        self.sku_table['adjustedQuantity'] = self.sku_table['rec_qty']
        self.sku_table['extended_sku_cost'] = self.sku_table['quantity'] * self.sku_table['unitPrice']
        self.sku_table['adjustedUnitPrice'] = self.sku_table['extended_sku_cost'] / self.sku_table['adjustedQuantity']
        self.sku_table['ext_po_cost']= self.sku_table['po_price'] * self.sku_table['rec_qty']
        self.sku_table['percent_difference'] = abs(self.sku_table['ext_po_cost'] - self.sku_table['extended_sku_cost']) / (self.sku_table['extended_sku_cost'])

    def invoice2df(queue_position, queue):
        """Grabs needed data to create a dataframe of information on each SKU. The resulting DataFrame is used to patch values on the API website.

        Args:
            queue_position (int): position of invoice in line item resolution queue dictionary
            lir_queue : accessing the lir_queue attributes
        """
        invoice = Invoice(queue_position, queue)
        invoice.get_job_info(queue)
        invoice.get_api_sku_info(queue)
        invoice.get_po_details(queue)
        invoice.get_receiving_details(queue)
        invoice.calculate_cost()


    def patch_data(self, lir_queue):
        """ Patches data with PATCH operation to REST interface. Data is patched SKU by SKU
            Etag isfor 'if-match' header required by PATCH operation
        Args:
            lir_queue : accessing the lir_queue attributes
        """
        for idx, sku_id in enumerate(self.sku_table.documentDetailId):
            etag_url = f"https://{lir_queue.hostname}apiclient.com/CHPAPO/v2/documentdetails/{sku_id}"
            payload = ""
            etag = requests.request("GET", etag_url, headers=lir_queue.headers, data=payload).headers['Etag']
            adjusted_qty_topatch = str(self.sku_table['adjustedQuantity'][idx])
            adjusted_price_topatch = str(self.sku_table['adjustedUnitPrice'][idx])
            patch_payload = json.dumps([{"path": "/adjustedQuantity","op": "replace","value": adjusted_qty_topatch},{"path": "/adjustedUnitPrice","op": "replace","value": adjusted_price_topatch}])
            patch_headers = {
                            "accept": "application/json",
                            "Authorization": f"Bearer {lir_queue.auth_token}",
                            "If-Match": etag,
                            "Content-Type": "application/json-patch+json"}
            patch_request = requests.request("PATCH", etag_url, headers=patch_headers, data=patch_payload)

    def compare_dfs(selenium_df, api_df, document_number):
        """ Standardizes and compares two DataFrames for testing purposes. Tests for equivalency.

        Args:
            selenium_df (DataFrame): DataFrame created from previous Selenium method
            api_df (DataFrame): DataFrame created from new REST API method
            document_number (str): document number, shared key between the two DataFrames

        Returns:
            Tuple: tuple containing document number and bool representing equivalency
        """
        selenium_df = selenium_df.sort_values(by = 'sku_number')
        selenium_df = selenium_df.reset_index(drop=True)
        selenium_df = selenium_df.astype(float)
        selenium_df.columns =  ['quantity', 'unitPrice', 'adjustedQuantity', 'adjustedUnitPrice',
        'sku_number', 'po_price', 'rec_qty', 'extended_sku_cost', 'ext_po_cost',
        'percent_difference']
        api_df = api_df.drop(columns = ['documentDetailId', 'po_detail_idl', 'sku_description', 'detail_id', 'po_detail_idr'])
        api_df = api_df.sort_values(by = 'sku_number')
        api_df = api_df.reset_index(drop=True)
        api_df = api_df.astype(float)
        t = (api_df.values == selenium_df.values).all()
        return document_number, t

    def test(api_dict, selenium_dict):
        """ Loops through generated API and Selenium dictionaries and compares DataFrames with shared keys(document numbers), testing for equivilancy.
            Used for testing
        Args:
            api_dict (dict): dictionary of DataFrames created from REST API process
            selenium_dict (dict): dictionary of DataFrames created from previous Selenium process

        Returns:
            list: list of tuples. Each element containing document number and bool representing equivalency
        """
        equal_keys = set(api_dict.keys()).intersection(set(selenium_dict.keys()))
        test_results = []
        for document_number in equal_keys:
            t = Invoice.compare_dfs(selenium_dict[str(document_number)], api_dict[str(document_number)], str(document_number))
            test_results.append(t)
        return test_results


def main(testing=False, size='', hostname = 'test.'):
    """ Creates dataframes for each invoice in the line item resolution queue and patches calculated values.
        If testing==True, compares DataFrames from the new REST method against the previous Selenium method.

    Args:
        testing (bool, optional): Whether to run testing against Selenium method. Defaults to False.
        size (str, optional): Number of invoices to instantiate from the queue. Defaults to '' but can be changed to a smaller value for testing purposes.
        hostname (str, optional): Used to quickly switch calls between TEST and PROD environments

    Returns:
        list: list of tuples. Only returns a list if testing==True. Each element contains a document number and bool representing equivalency
        Otherwise, the values are patched and nothing is returned.
    """
    logger = logging.getLogger(__name__)
    try:
        lir_queue = Testing_LIR(size=size, hostname=hostname)
        logger.info('Queue Created')
    except:
        logger.error('Queue Creation Failed')
    api_dict = {}
    for queue_position in range(lir_queue.number_invoices):
        try:
            invoice = Invoice(queue_position, lir_queue)
        except:
            logger.info('Creating initial queue dictionary failed')
        try:
            invoice.get_job_info(lir_queue)
        except:
            logger.error('Getting job info failed')
        try:
            invoice.get_api_sku_info(lir_queue)
        except:
            logger.error('Getting api_sku_info_failed')
        try:
            invoice.get_po_details(lir_queue)
        except:
            logger.error('Failed to get PO info')
        try:
            invoice.get_receiving_details(lir_queue)
        except:
            logger.error('Failed to get Receiving Information')
        invoice.calculate_cost()
        try:
            invoice.patch_data(lir_queue)
        except:
            logger.error('Failed to Patch Data')
        api_dict[invoice.document_number] = invoice.sku_table
        logger.info(f'Invoice position {queue_position} logged!')
    if testing == True:
        logger.info(f'Testing Enabled: Grabbing Selenium Dataframes for comparison')
        selenium_dict = get_selenium_dict()
        results = Invoice.test(api_dict, selenium_dict)
        logger.info(f'Testing Results: {results}')
        return results

if __name__ == '__main__':
    os.remove("logging_info.log")
    load_dotenv(find_dotenv())
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(filename = 'logging_info.log', level=logging.INFO, format=log_fmt)
    #size is set at 2 for testing
    main(testing=True, size='')
